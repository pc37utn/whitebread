from lxml import etree
import requests
import os
from PIL import Image
from io import BytesIO


class Set:
    def __init__(self, search_string, yaml_settings):
        self.size = 0
        self.results = []
        self.request = search_string
        self.settings = yaml_settings

    def __repr__(self):
        return f"A set of records based on the following http request:\n\t{self.request}."

    def __str__(self):
        return f"A set of records based on the following http request:\n\t{self.request}."

    def populate(self, session_token=""):
        document = etree.parse(f"{self.request}{session_token}")
        token = document.findall('//{http://www.fedora.info/definitions/1/0/types/}token')
        results = document.findall('//{http://www.fedora.info/definitions/1/0/types/}pid')
        for result in results:
            self.results.append(result.text)
            self.size += 1
        if len(token) == 1:
            token_value = document.findall('//{http://www.fedora.info/definitions/1/0/types/}token')[0].text
            new_token = f"&sessionToken={token_value}"
            self.populate(new_token)
        else:
            return f"Added {self.results} to cluster."

    def harvest_metadata(self, dsid=None):
        if dsid is None:
            dsid = self.settings["default_dsid"]
        if self.settings["destination_directory"] in os.listdir("."):
            pass
        else:
            os.mkdir(self.settings["destination_directory"])
        ext = get_extension(dsid)
        for result in self.results:
            r = requests.get(f"{self.settings['fedora_path']}:{self.settings['port']}/fedora/objects/{result}/"
                             f"datastreams/{dsid}/content",
                             auth=(f"settings['username']", f"settings['password']"))
            if r.status_code == 200:
                new_name = result.replace(":", "_")
                print(f"Downloading {dsid} for {result}.")
                with open(f"{self.settings['destination_directory']}/{new_name}{ext}", "w") as new_file:
                    new_file.write(r.text)
            else:
                print(f"Could not harvest metadata for {result}: {r.status_code}.")

    def grab_images(self, dsid=None):
        if self.settings["destination_directory"] in os.listdir("."):
            pass
        else:
            os.mkdir(self.settings["destination_directory"])
        if dsid is None:
            dsid = self.settings["default_dsid"]
        ext = get_extension(dsid)
        for result in self.results:
            r = requests.get(f"{self.settings['fedora_path']}:{self.settings['port']}/fedora/objects/{result}/"
                             f"datastreams/{dsid}/content",
                             auth=(f"settings['username']", f"settings['password']"))
            print(f"Downloading the {dsid} datastream for {result}.")
            in_file = Image.open(BytesIO(r.content))
            new_name = result.replace(":", "_")
            in_file.save(f"{self.settings['destination_directory']}/{new_name}{ext}")

    def grab_other(self, dsid=None):
        if self.settings["destination_directory"] in os.listdir("."):
            pass
        else:
            os.mkdir(self.settings["destination_directory"])
        if dsid is None:
            dsid = self.settings["default_dsid"]
        ext = get_extension(dsid)
        for result in self.results:
            r = requests.get(f"{self.settings['fedora_path']}:{self.settings['port']}/fedora/objects/{result}/"
                             f"datastreams/{dsid}/content",
                             auth=(f"settings['username']", f"settings['password']"))
            if r.status_code == 200:
                print(f"Downloading the {dsid} datastream for {result}.")
                new_name = result.replace(":", "_")
                with open(f"{self.settings['destination_directory']}/{new_name}{ext}", 'wb') as other:
                    other.write(r.content)
            else:
                print(f"Failed to download {dsid} for {result} with {r.status_code}.")

    def size_of_set(self):
        return f"Total records: {len(self.results)}"

    def update_gsearch(self):
        successes = 0
        for result in self.results:
            r = requests.post(f"{self.settings['fedora_path']}:{self.settings['port']}/fedoragsearch/rest?"
                              f"operation=updateIndex&action=fromPid&value={result}",
                              auth=(self.settings["gsearch_username"], self.settings["gsearch_password"]))
            if r.status_code == 200:
                successes += 1
                print(f"Successfully updated record for {result} with gSearch.")
            else:
                print(f"Failed to update gsearch for {result} with {r.status_code} status code.")
        print(f"\nSuccessfully updated {successes} records.")
        return

    def mark_as_missing(self, dsid=None):
        print(f"Finding results that are missing a {dsid} datastream.")
        missing = []
        for i in self.results:
            r = requests.get(f"{self.settings['fedora_path']}:{self.settings['port']}/fedora/"
                             f"objects/{i}/datastreams/{dsid}", auth=(f"{self.settings['username']}",
                                                                      f"{self.settings['password']}"))
            if r.status_code != 200:
                missing.append(i)
        print(f"{len(missing)} of {len(self.results)} were missing a {dsid} datastream.")
        return missing

    def get_relationships(self):
        for i in self.results:
            r = requests.get(f"{self.settings['fedora_path']}:{self.settings['port']}/fedora/"
                             f"objects/{i}/relationships", auth=(f"{self.settings['username']}",
                                                                      f"{self.settings['password']}"))
            if r.status_code == 200:
                print(r.text)

    def find_rels_ext_relationship(self, relationship):
        membership_list = []
        print(f"Finding {relationship} objects for items in result list.")
        for i in self.results:
            predicate = "&predicate=info:fedora/fedora-system:def/relations-external#" \
                        f"{relationship}".replace(":", "%3a").replace("/", "%2f").replace("#", "%23")
            r = requests.get(f"{self.settings['fedora_path']}:{self.settings['port']}/fedora/"
                             f"objects/{i}/relationships?subject=info%3afedora%2f{i}&format=turtle{predicate}",
                             auth=(f"{self.settings['username']}", f"{self.settings['password']}"))
            if r.status_code == 200:
                new_list = r.text.split(">")
                if len(new_list) == 4:
                    new_item = {"pid": i,
                                f"{relationship}": new_list[2].replace("<info:fedora/", "").replace(" ", "")}
                    membership_list.append(new_item)
        print(membership_list)
        return membership_list

    def list_dsids(self):
        for result in self.results:
            print(f"Finding dsids for {result}.\n")
            url = f"{self.settings['fedora_path']}:{self.settings['port']}/fedora/objects/{result}/datastreams?profiles=true"
            print(url)
            r = requests.get(url, auth=(f"{self.settings['username']}", f"{self.settings['password']}"))
            if r.status_code == 200:
                print(r.text)
            else:
                print(r.status_code)

class log_file:
    def __init__(self, log_location="logs/whitebread.log"):
        self.location = log_location

    def append(self, message):
        try:
            with open(self.location, "a") as file:
                file.write(message)
        except:
            print(f"Can't write to {self.location}.")


def get_extension(dsid):
    datastream_extensions = {
        "TN": ".jpg",
        "OBJ": ".tif",
        "JP2": ".jp2",
        "JPG": ".jpg",
        "MODS": ".xml",
        "DC": ".xml",
        "TRANSCRIPT": ".txt"
    }
    return datastream_extensions[dsid]