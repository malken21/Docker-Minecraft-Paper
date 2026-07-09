import sys
import urllib.request
import json
import hashlib
import os
import time

USER_AGENT = 'docker-minecraft-paper-builder/1.0 (contact: malken21)'

def parse_version(v_str):
    if '-' in v_str:
        return None
    parts = []
    for p in v_str.split('.'):
        if p.isdigit():
            parts.append(int(p))
        else:
            return None
    while len(parts) < 3:
        parts.append(0)
    return parts

def get_latest_build(version):
    url = f'https://fill.papermc.io/v3/projects/paper/versions/{version}/builds'
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req) as response:
            builds = json.loads(response.read().decode('utf-8'))
            if not builds:
                return None
            latest = builds[0]
            build_num = latest['id']
            downloads = latest.get('downloads', {})
            server_info = downloads.get('server:default')
            if not server_info:
                keys = list(downloads.keys())
                if keys:
                    server_info = downloads[keys[0]]
            
            if server_info:
                return {
                    'version': version,
                    'build': str(build_num),
                    'tag': f"{version}-{build_num}",
                    'file': server_info['name'],
                    'sha256': server_info['checksums']['sha256'],
                    'url': server_info['url']
                }
    except Exception as e:
        sys.stderr.write(f"Error fetching builds for {version}: {e}\n")
    return None

def verify_url_exists(url):
    req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req) as response:
            return response.getcode() == 200
    except Exception as e:
        sys.stderr.write(f"HEAD request failed for {url}: {e}\n")
        return False

def get_matrix():
    url = 'https://fill.papermc.io/v3/projects/paper'
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        sys.stderr.write(f"Error fetching project data: {e}\n")
        return {"include": []}

    versions = []
    for group, v_list in data.get('versions', {}).items():
        for v in v_list:
            parsed = parse_version(v)
            if parsed and parsed[0] == 1 and parsed >= [1, 21, 4]:
                versions.append(v)
    
    versions.reverse() # 古い順
    
    matrix = []
    for v in versions:
        build_info = get_latest_build(v)
        if build_info:
            if verify_url_exists(build_info['url']):
                matrix.append(build_info)
            else:
                sys.stderr.write(f"Skipping version {v} because download URL returns non-200 status.\n")
        time.sleep(0.5)
        
    # 最新のMinecraftバージョン（リストの最後の要素）にフラグを設定
    if matrix:
        for item in matrix:
            item['is_latest'] = False
        matrix[-1]['is_latest'] = True
        
    return {"include": matrix}

def download_file(path, url, expected_sha256):
    dir_path = os.path.dirname(path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)
        
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    sys.stderr.write(f"Downloading {url} to {path}...\n")
    
    try:
        with urllib.request.urlopen(req) as response:
            data = response.read()
    except Exception as e:
        sys.stderr.write(f"Download failed: {e}\n")
        sys.exit(1)
        
    # SHA256 検証
    sha256_hash = hashlib.sha256(data).hexdigest()
    if sha256_hash != expected_sha256:
        sys.stderr.write(f"SHA256 mismatch! Expected {expected_sha256}, got {sha256_hash}\n")
        sys.exit(1)
        
    with open(path, 'wb') as f:
        f.write(data)
    sys.stderr.write("Download and verification successful.\n")

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage:\n  python updatePaper.py get-matrix\n  python updatePaper.py download <path> <url> <sha256>\n")
        sys.exit(1)
        
    mode = sys.argv[1]
    if mode == 'get-matrix':
        matrix_data = get_matrix()
        print(json.dumps(matrix_data))
    elif mode == 'download':
        if len(sys.argv) < 5:
            sys.stderr.write("Usage: python updatePaper.py download <path> <url> <sha256>\n")
            sys.exit(1)
        path = sys.argv[2]
        url = sys.argv[3]
        sha256 = sys.argv[4]
        download_file(path, url, sha256)
    else:
        sys.stderr.write(f"Unknown mode: {mode}\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
