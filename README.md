# Docker-Minecraft-Paper

最低限の PaperMC の Docker イメージ

## [updatePaper.py](/updatePaper.py)

指定した PaperMC の jar ファイルが最新版ではない場合、最新版をダウンロードするスクリプト

すでに最新版を導入している場合はダウンロードされない

```sh
# PaperMC の 1.20.4 の最新ビルドをダウンロードする場合
python3 updatePaper.py ./paper.jar "1.20.4"
```
