# ReadMe https://www.linkedin.com/pulse/connect-splunk-cloudhealth-using-rest-api-zhenrong-daniel-han

# Python3.6
import requests, json, datetime, time

# Generate log file for this python scripe
log_file = open("python_log.log", "w")
 
# Splunk search query to search avg, min, max CPU and Memory usage within the past 60 minutes.
splunk_search_query = {
  'search': 'search index=* (object=Memory counter="Available Bytes") OR ( object=Processor counter="% Processor Time" instance=_Total) | eval AvailableBytes=if(counter=="Available Bytes", Value, null()) | eval CPUUsagePercent=if(counter=="% Processor Time", Value, null()) | stats min(AvailableBytes) as AvailableBytesmin, max(AvailableBytes) as AvailableBytesmax, avg(AvailableBytes) as AvailableBytesavg, min(CPUUsagePercent) as CPUUsagePercentmin, max(CPUUsagePercent) as CPUUsagePercentmax, avg(CPUUsagePercent) as CPUUsagePercentavg by host\n',
  'earliest_time': '-60m',
  'latest_time': 'now'
}
 
# Splunk API Call to Post/Create a Splunk search job using the query above. The response is Splunk SearchID: sid
response_splunk = requests.post('https://your-company.splunkcloud.com:8089/services/search/jobs', data=splunk_search_query, verify=False, auth=('your-splunk-acct@yourcompany.com', 'replace-with-real-password'))
sid = response_splunk.text.splitlines()[2].split("<sid>")[1].split("</sid>")[0]
print(sid)
log_file.write(sid)
log_file.writelines("\n")
 
# Wait 60 sec allowing the search job to complete.
time.sleep(60)
 
# Add returned SID into the middle of URL
urlStringPart1 = 'https://yourcompany.splunkcloud.com:8089/services/search/jobs/'
urlStringPart2 = '/results?output_mode=json&count=0'
wholeUrl = urlStringPart1 + sid + urlStringPart2
 
# Splunk API Call to get Splunk search result
r = requests.get(wholeUrl, verify=False, auth=('your-splunk-acct@yourcompany.com', 'replace-with-real-password'))
splunk_result = json.loads(r.text)
# print(r)
# print(r.text)
# print(type(splunk_result['results']))
splunk_list = splunk_result['results']
print(splunk_list)
log_file.write(str(splunk_list))
log_file.writelines("\n")
 
# CloudHealth API Call Header for querying instance-id, aws-account-id and memory size.
headers = {
    'Authorization': 'Bearer <API KEY>',
}
 
# CloudHealth API Call Header for posting metrics data
headers2 = {
    'Authorization': 'Bearer <API KEY>',
    'Content-Type': 'application/json',
}
 
# CloudHealth's required API metrics keys format
standard_string = '{"metrics":{"datasets":[{"metadata":{"assetType":"aws:ec2:instance","granularity":"hour","keys":["assetId","timestamp","memory:free:bytes.min","memory:free:bytes.max","memory:free:bytes.avg","cpu:used:percent.min","cpu:used:percent.max","cpu:used:percent.avg","memory:size:bytes.avg","memory:size:bytes.min","memory:size:bytes.max","memory:used:percent.avg","memory:used:percent.min","memory:used:percent.max"]},"values":[['
 
end_string = ']]}]}}'
 
# for loop in each row/host of Splunk search result
for row in splunk_list:
    hostname = row['host']
 
    # if hostname is an IP, query instance-id using private IP
    if hostname.split(".")[0].isnumeric():
        Params = (
            ('', ''),
            ('api_version', '2'),
            ('name', 'AwsInstance'),
            ('query', 'private_ip=\'' + hostname + '\''),
            ('fields', 'instance_id,account.owner_id,instance_type.memory'),
        )
 
    # if hostname is not an IP, query instance-id using hostname
    else:
        Params = (
            ('', ''),
            ('api_version', '2'),
            ('name', 'AwsInstance'),
            ('query', 'name=\'' + hostname + '\''),
            ('fields', 'instance_id,account.owner_id,instance_type.memory'),
        )
 
    # CloudHealth API Call to query instance-id, aws-account-id and memory size
    response = requests.get('https://chapi.cloudhealthtech.com/api/search', headers=headers, params=Params)
    c10_result = json.loads(response.text)
 
    # if CloudHealth couldn't find the instance, skip it.
    if len(c10_result) == 0:
        continue
 
    instance_id = c10_result[0]['instance_id']
    aws_account_id = c10_result[0]['account']['owner_id']
    memory_size = c10_result[0]['instance_type']['memory']
    arn = 'ap-southeast-2:' + str(aws_account_id) + ':' + instance_id
 
    # CloudHealth API only supports HOURLY so we have to strip minutes from timestamp
    timestamp = str((datetime.datetime.utcnow() - datetime.timedelta(hours=1)).isoformat()).split(':')[0] + ':00:00'
 
    memory_free_bytes_min = int(row['AvailableBytesmin'])
    memory_free_bytes_max = int(row['AvailableBytesmax'])
    memory_free_bytes_avg = int(float(row['AvailableBytesavg']))
    cpu_used_percent_min = round(float(row['CPUUsagePercentmin']), 2)
    cpu_used_percent_max = round(float(row['CPUUsagePercentmax']), 2)
    cpu_used_percent_avg = round(float(row['CPUUsagePercentavg']), 2)
 
    # Convert GB to Byte
    memory_size_bytes_avg = (int(memory_size))*1024*1024
    memory_size_bytes_min = (int(memory_size))*1024*1024
    memory_size_bytes_max = (int(memory_size))*1024*1024
 
    memory_used_percent_avg = round(((memory_size_bytes_avg - memory_free_bytes_avg)/memory_size_bytes_avg)*100, 2)
    memory_used_percent_min = round(((memory_size_bytes_avg - memory_free_bytes_max)/memory_size_bytes_avg)*100, 2)
    memory_used_percent_max = round(((memory_size_bytes_avg - memory_free_bytes_min)/memory_size_bytes_avg)*100, 2)
 
    # Combine metrics into one long string
    metrics_all_values_str = '"' + arn + '"' + ',' + ' "' + timestamp + '"' + ', ' + str(memory_free_bytes_min) + ', ' + str(memory_free_bytes_max) + ', ' + str(memory_free_bytes_avg) + ', ' + str(cpu_used_percent_min) + ', ' + str(cpu_used_percent_max) + ', ' + str(cpu_used_percent_avg) + ', ' + str(memory_size_bytes_avg) + ', ' + str(memory_size_bytes_min) + ', ' + str(memory_size_bytes_max) + ', ' + str(memory_used_percent_avg) + ', ' + str(memory_used_percent_min) + ', ' + str(memory_used_percent_max)
    combined_string = standard_string + metrics_all_values_str + end_string
    print(combined_string)
    log_file.write(combined_string)
    log_file.writelines("\n")
 
    # CloudHealth API Call to post metrics
    response2 = requests.post('https://chapi.cloudhealthtech.com/metrics/v1', headers=headers2, data=combined_string)
    print(response2)
    log_file.write(str(response2))
    log_file.writelines("\n")
    print(response2.text)
    log_file.write(response2.text)
    log_file.writelines("\n")
 
    # Wait 1 sec to avoid CloudHealth API throttle: max 60 POST requests are allowed per minute.
    time.sleep(1)
 
log_file.close()
