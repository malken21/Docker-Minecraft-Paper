import sys
import urllib.request
import json
import hashlib
import os
import time
import zipfile
import struct
import re

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

def get_recent_builds(version, limit=10):
    url = f'https://fill.papermc.io/v3/projects/paper/versions/{version}/builds'
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req) as response:
            builds = json.loads(response.read().decode('utf-8'))
            if not builds:
                return []
            
            recent_builds = []
            for b in builds[:limit]:
                build_num = b['id']
                downloads = b.get('downloads', {})
                server_info = downloads.get('server:default')
                if not server_info:
                    keys = list(downloads.keys())
                    if keys:
                        server_info = downloads[keys[0]]
                
                if server_info:
                    recent_builds.append({
                        'version': version,
                        'build': str(build_num),
                        'tag': f"{version}-{build_num}",
                        'file': server_info['name'],
                        'sha256': server_info['checksums']['sha256'],
                        'url': server_info['url']
                    })
            return recent_builds
    except Exception as e:
        sys.stderr.write(f"Error fetching builds for {version}: {e}\n")
    return []

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
        builds_info = get_recent_builds(v, limit=10)
        builds_info.reverse() # 古いビルドから順に追加
        for build_info in builds_info:
            if verify_url_exists(build_info['url']):
                matrix.append(build_info)
            else:
                sys.stderr.write(f"Skipping version {v} build {build_info['build']} because download URL returns non-200 status.\n")
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

def get_jar_java_version(jar_path):
    if not os.path.exists(jar_path):
        sys.stderr.write(f"Jar file not found: {jar_path}\n")
        return None
    
    try:
        with zipfile.ZipFile(jar_path, 'r') as z:
            # 優先してチェックする既知のエントリーポイントクラス
            priority_classes = [
                'net/minecraft/bundler/Main.class',
                'org/bukkit/craftbukkit/Main.class',
                'Main.class'
            ]
            for p_class in priority_classes:
                if p_class in z.namelist():
                    try:
                        with z.open(p_class) as f:
                            magic = f.read(4)
                            if magic == b'\xca\xfe\xba\xbe':
                                _, major = struct.unpack('>HH', f.read(4))
                                if major >= 45:
                                    return major - 44
                    except Exception:
                        pass

            # 見つからなかった場合は、最初に見つかったクラスファイルを使用する
            for name in z.namelist():
                if name.endswith('.class'):
                    try:
                        with z.open(name) as f:
                            magic = f.read(4)
                            if magic == b'\xca\xfe\xba\xbe':
                                _, major = struct.unpack('>HH', f.read(4))
                                if major >= 45:
                                    return major - 44
                    except Exception:
                        continue
    except Exception as e:
        sys.stderr.write(f"Error reading jar {jar_path}: {e}\n")
    return None

def get_dockerfile_java_version(dockerfile_path):
    if not os.path.exists(dockerfile_path):
        sys.stderr.write(f"Dockerfile not found: {dockerfile_path}\n")
        return None
    try:
        args = {}
        last_from_line = None
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                if stripped.startswith('ARG'):
                    parts = stripped.split()
                    if len(parts) >= 2:
                        arg_parts = parts[1].split('=', 1)
                        if len(arg_parts) == 2:
                            args[arg_parts[0]] = arg_parts[1]
                if stripped.startswith('FROM'):
                    last_from_line = stripped
                    
        if last_from_line:
            parts = last_from_line.split()
            if len(parts) >= 2:
                image = parts[1]
                for arg_name, arg_val in args.items():
                    image = image.replace(f"${{{arg_name}}}", arg_val)
                    image = image.replace(f"${arg_name}", arg_val)
                match = re.search(r'java(\d+)|openjdk:(\d+)|temurin:(\d+)|jdk-(\d+)|jre-(\d+)', image, re.IGNORECASE)
                if match:
                    for val in match.groups():
                        if val:
                            return int(val)
    except Exception as e:
        sys.stderr.write(f"Error reading Dockerfile {dockerfile_path}: {e}\n")
    return None

def verify_java_versions(jar_path, dockerfile_path):
    jar_ver = get_jar_java_version(jar_path)
    docker_ver = get_dockerfile_java_version(dockerfile_path)
    
    if jar_ver is None:
        sys.stderr.write(f"Could not determine Java version from jar file {jar_path}.\n")
        sys.exit(1)
    if docker_ver is None:
        sys.stderr.write(f"Could not determine Java version from Dockerfile {dockerfile_path}.\n")
        sys.exit(1)
        
    sys.stderr.write(f"Jar requires Java {jar_ver}. Dockerfile provides Java {docker_ver}.\n")
    
    if docker_ver < jar_ver:
        sys.stderr.write(f"Error: Dockerfile Java version ({docker_ver}) is lower than Jar required Java version ({jar_ver})!\n")
        sys.exit(1)
    
    sys.stderr.write("Java version verification passed.\n")

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage:\n  python updatePaper.py get-matrix\n  python updatePaper.py download <path> <url> <sha256>\n  python updatePaper.py verify-java <jar_path> <dockerfile_path>\n  python updatePaper.py get-jar-version <jar_path>\n")
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
    elif mode == 'verify-java':
        if len(sys.argv) < 4:
            sys.stderr.write("Usage: python updatePaper.py verify-java <jar_path> <dockerfile_path>\n")
            sys.exit(1)
        jar_path = sys.argv[2]
        dockerfile_path = sys.argv[3]
        verify_java_versions(jar_path, dockerfile_path)
    elif mode == 'get-jar-version':
        if len(sys.argv) < 3:
            sys.stderr.write("Usage: python updatePaper.py get-jar-version <jar_path>\n")
            sys.exit(1)
        jar_path = sys.argv[2]
        jar_ver = get_jar_java_version(jar_path)
        if jar_ver is None:
            sys.stderr.write(f"Could not determine Java version from jar file {jar_path}.\n")
            sys.exit(1)
        print(jar_ver)
    else:
        sys.stderr.write(f"Unknown mode: {mode}\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
