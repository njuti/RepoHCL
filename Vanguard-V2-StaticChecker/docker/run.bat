@echo off
:: TODO: 未测试
:: 提取库名和版本号
set input=%1
for %%F in (%input%) do set filename_no_ext=%%~nF
for /f "tokens=1,2 delims=-" %%a in ("%filename_no_ext%") do (
    set library=%%a
    set version=%%b
)
if "%version%"=="" set version=latest

echo Library Name: %library%
echo Version: %version%

docker build -f docker\base.dockerfile -t cg  .
docker build -f "%1" -t cg_%library%:%version%  --progress=plain .

for /f %%i in ('docker create cg_%library%:%version%') do set container_id=%%i

mkdir ..\output\%filename_no_ext%
docker cp %container_id%:/root/output/cg.dot ..\output\%filename_no_ext%
docker cp %container_id%:/root/output/functions.json ..\output\%filename_no_ext%\
docker cp %container_id%:/root/output/structs.json ..\output\%filename_no_ext%\
docker cp %container_id%:/root/output/records.json ..\output\%filename_no_ext%\
docker cp %container_id%:/root/output/typedefs.json ..\output\%filename_no_ext%\
docker cp %container_id%:/root/vanguard/cmake-build-debug/tools/CallGraphGen/cge ..\lib\
docker cp %container_id%:/root/resource/origin ..\resource\%filename_no_ext%
docker stop %container_id%
docker rm %container_id%
docker image prune -f