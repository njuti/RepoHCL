#!/bin/bash

# source docker/run.sh <lib>
# example: source docker/run.sh xxx.dockerfile

# 提取库名和版本号
input=$1
filename_no_ext=${input##*/}  # 移除最后一个 / 及其之前的部分
filename_no_ext=${filename_no_ext%.dockerfile}  # 移除 .dockerfile 扩展名
if [[ "$filename_no_ext" == *-* ]]; then
  library=${filename_no_ext%-*}
  version=${filename_no_ext#*-}
else
  library=$filename_no_ext
  version="latest"
fi

echo "Library Name: $library"
echo "Version: $version"

docker build -f docker/base.dockerfile -t cg .
docker build -f "$1" -t cg_"$library":"$version"  --progress=plain .

container_id=$(docker create cg_"$library":"$version")

mkdir -p ../output/"${filename_no_ext}"
docker cp "${container_id}":/root/output/cg.dot ../output/"${filename_no_ext}"
docker cp "${container_id}":/root/output/functions.json ../output/"${filename_no_ext}"/
docker cp "${container_id}":/root/output/structs.json ../output/"${filename_no_ext}"/
docker cp "${container_id}":/root/output/records.json ../output/"${filename_no_ext}"/
docker cp "${container_id}":/root/output/typedefs.json ../output/"${filename_no_ext}"/
docker cp "${container_id}":/root/vanguard/cmake-build-debug/tools/CallGraphGen/cge ../lib/
docker cp "${container_id}":/root/resource/origin ../resource/"${filename_no_ext}"
docker stop "${container_id}"
docker rm "${container_id}"
docker image prune -f