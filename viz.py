import kagglehub
import shutil
import os

# 1. Download the latest version
path = kagglehub.dataset_download("arshadshemilk/vizar-orbit")

# 2. Define your destination (e.g., a folder named 'data' in your git workspace)
destination = './vizar-orbit-data'

# 3. Copy the content
try:
    if os.path.exists(destination):
        print(f"Directory {destination} already exists. Removing old version...")
        shutil.rmtree(destination)
    
    shutil.copytree(path, destination)
    print(f"Dataset successfully copied to: {os.path.abspath(destination)}")
except Exception as e:
    print(f"Error copying files: {e}")