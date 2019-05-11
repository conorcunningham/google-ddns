# Google Cloud Dynamic DNS Client

This is a simple dynamic DNS script for Google Cloud DNS. The script will check for its public IP address, and then based on its configuration it read from the configuration file, check whether Google Cloud DNS has a corresponding DNS entry. If no corresponding entry is found, the script will create one. If a corresponding entry is found, but has an IP address which doesn't match that of what the script found, then the script will update then Google Cloud entry (read delete, then create). Finally, if the scripts configuration file matches that of the Google Cloud DNS entry, then it will sleep for an interval of x, and the process repeats.

This project consists of the following components:

- **gcloud-ddns.py**: the dynamic dns client script
- **ddns-conf.json**: programs configuration file
- **requirements.txt**: requirements to be installed

```bash
Usage: python gcloud-ddns.py <path_to_configuration_file.json>
```

### Authentication 
In order to use the Google Cloud API, you will need an API key for your account. This key will be a json file. The script will check for a command line argument for the configuration file, but if none is given it will look for ddns-api-key.json in the same directory as the script.

The script will set **GOOGLE_APPLICATION_CREDENTIALS** environmental variable to the path of your API key.

```python
# You can provide the API key as the first parameter
    if len(sys.argv) == 2:
        api_key = sys.argv[1]
    elif len(sys.argv) > 2:
        print("Usage: python gcloud-ddns.py [path_to_api_credentials.json]")
        return 1
    else:
        api_key = "ddns-api-key.json"
        
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = api_key
```

### Configuration file
The configuration for the script is read from a json file. Here are the contents of the example [ddns-conf.json](ddns-conf.json) file
``` json
{
  "host": "firewall.example.com.",
  "project_id": "fluffy-penguin-242411",
  "managed_zone": "example",
  "domain": "example.com",
  "ttl": 60,
  "interval": 600
}
```
Should you wish to change the name of the config file, you can edit it in the script
```python
config_file = "ddns-conf.json"
```

- **host**: the fully-qualified domain name of the host you want to set. *_NB_** You must include the . after the .com. This is a Google requirement/
- **project_id**: Your project ID within Google Cloud
- **managed_zone**: The name of your managed zone in Google Cloud
- **domain**: Your domain name
- **ttl**: The number of seconds for the TTL
- **interval**: How long the script will sleep before running again

### ipify.org API
This project makes use of the snazzy [ipify.org](https://www.ipify.org) API for fetching the clients public IP address.

### Usage
This program is free to all. Proper credit should be given if reusing. I am open to improvements and all constructive feedback.