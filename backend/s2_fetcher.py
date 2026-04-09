import requests
import json
import os
import gzip
from datetime import datetime

class S2DatasetManager:
    def __init__(self, api_key=None):
        self.base_url = "https://api.semanticscholar.org/datasets/v1"
        self.headers = {"x-api-key": api_key} if api_key else {}

    def get_latest_release(self):
        url = f"{self.base_url}/release/latest"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_dataset_files(self, release_id, dataset_name):
        url = f"{self.base_url}/release/{release_id}/dataset/{dataset_name}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json().get('files', [])

    def download_sample(self, file_url, output_path):
        print(f"Downloading sample from {file_url}...")
        response = requests.get(file_url, stream=True)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Saved to {output_path}")

    def process_sample(self, file_path, limit=10):
        print(f"Processing first {limit} records from {file_path}...")
        results = []
        with gzip.open(file_path, 'rt') as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                results.append(json.loads(line))
        return results

if __name__ == "__main__":
    # Example usage:
    # Get your S2_API_KEY from env if you have one
    s2 = S2DatasetManager(api_key=os.environ.get("S2_API_KEYS", "").split(",")[0].strip())
    
    try:
        latest = s2.get_latest_release()
        release_id = latest['release_id']
        print(f"Latest Release ID: {release_id}")
        
        # List available datasets
        print("\nAvailable Datasets:")
        for ds in latest['datasets']:
            print(f"- {ds['name']}: {ds['description']}")
            
        # Example: Fetch files for 'papers' dataset
        # Warning: These files are huge (GBs). Don't download full files unless you have space.
        # files = s2.get_dataset_files(release_id, "papers")
        # if files:
        #     s2.download_sample(files[0], "papers_sample.json.gz")
        #     records = s2.process_sample("papers_sample.json.gz", limit=5)
        #     print(json.dumps(records, indent=2))
            
    except Exception as e:
        print(f"Error: {e}")
