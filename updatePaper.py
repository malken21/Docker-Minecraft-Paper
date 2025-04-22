from urllib import request
import json
from sys import argv
import hashlib
import os


# jarファイルパス
PATH = argv[1]
# バージョン
VERSION = argv[2]


def getBuildObj(Name: str, Version: str):
    # 最新のビルド 取得
    with request.urlopen(f"https://api.papermc.io/v2/projects/{Name}/versions/{Version}/builds") as response:
        builds = [item for item in json.load(response)["builds"]
                  if item["channel"] == "default"]
        if (len(builds) == 0):
            return None
        item = builds[-1]
        BUILD = item["build"]
        FILE = item["downloads"]["application"]["name"]
        SHA256 = item["downloads"]["application"]["sha256"]
    # 最新バージョンの情報を出力
    return {
        "name": Name,
        "version": Version,
        "build": BUILD,
        "file": FILE,
        "sha256": SHA256
    }


def getFile_sha256(path: str):
    hash = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            # ファイルをチャンクごとに読み込んでハッシュを計算
            for byte_block in iter(lambda: f.read(4096), b""):
                hash.update(byte_block)
    except FileNotFoundError:
        return None
    # sha256 のハッシュ値を return
    return hash.hexdigest()


def downloadLatest(LatestObj: object, path: str):
    # URL
    URL = f"https://api.papermc.io/v2/projects/{LatestObj['name']}/versions/{LatestObj['version']}/builds/{LatestObj['build']}/downloads/{LatestObj['file']}"
    # フォルダが存在しない場合は作成
    dir_path = os.path.dirname(path)
    if not os.path.exists(dir_path) and not os.path.isfile(path):
        os.makedirs(dir_path)
    # ファイル ダウンロード
    binary = request.urlopen(URL).read()
    with open(path, mode="wb") as f:
        f.write(binary)

    return path


LatestObj = getBuildObj("paper", VERSION)
if (LatestObj is None):
    exit(1)

# 最新版のハッシュ値
sha256_cloud = LatestObj["sha256"]

# ローカルのハッシュ値
sha256_local = getFile_sha256(PATH)

# 最新版とローカルのハッシュ値が違う場合
if sha256_cloud != sha256_local:
    # ダウンロードする
    print(
        f"Download: {LatestObj['name']}-{LatestObj['version']}-{LatestObj['build']}"
    )
    path = downloadLatest(LatestObj, PATH)
    print(f"Done: {path}")
