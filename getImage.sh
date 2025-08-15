#!/bin/bash
SCRIPT_DIR=$(dirname "$0")
TMP_DIR="tmp"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
if [ -z "$GITHUB_ACTIONS" ]; then
    current_fd_limit=$(ulimit -n)
    if [ "$current_fd_limit" -lt 4096 ]; then
        echo "增加文件描述符限制到4096（原限制：$current_fd_limit）"
        ulimit -n 4096 || echo "警告: 无法增加文件描述符限制,可能需要root权限"
    fi
    current_proc_limit=$(ulimit -u)
    if [ "$current_proc_limit" -lt 4096 ]; then
        echo "增加进程数限制到4096（原限制：$current_proc_limit）"
        ulimit -u 4096 || echo "警告: 无法增加进程数限制,可能需要root权限"
    fi
fi
echo "正在下载ygoprodeck卡片数据..."
curl -s https://db.ygoprodeck.com/api/v7/cardinfo.php | jq . > "$TMP_DIR/ygoprodeck_cardinfo.json"
THREAD_NUM=200
echo "正在提取卡片图片URL..."
jq -r '.data[].card_images[].image_url_cropped' "$TMP_DIR/ygoprodeck_cardinfo.json" > "$TMP_DIR/image_urls.txt"
TOTAL=$(wc -l < "$TMP_DIR/image_urls.txt")
rm -f "$TMP_DIR/ygoprodeck_cardinfo.json"
if [ $TOTAL -eq 0 ]; then
    echo "错误: 没有找到图片URL,请检查JSON文件是否有效"
    exit 1
fi
cat > "$TMP_DIR/download_worker.sh" << 'EOF'
#!/bin/bash
url="$1"
filename=$(basename "$url")
output_path="tmp/$filename"
final_png_path="${output_path%.jpg}.png"
if [[ ! -f "$final_png_path" ]]; then
    temp_path="${output_path}.tmp"
    wget -q --timeout=30 --tries=3 --retry-connrefused --waitretry=1 "$url" -O "$temp_path"
    if [ $? -ne 0 ]; then
        echo "下载失败: $url"
        rm -f "$temp_path" 2>/dev/null
        exit 1
    fi
    if [ ! -s "$temp_path" ]; then
        echo "删除空文件: $temp_path"
        rm -f "$temp_path"
        exit 1
    fi
    if ! magick identify "$temp_path" &>/dev/null; then
        echo "删除损坏的图片: $temp_path"
        rm -f "$temp_path"
        exit 1
    fi
    if magick "$temp_path" "$final_png_path"; then
        if ! magick identify "$final_png_path" &>/dev/null || [ ! -s "$final_png_path" ]; then
            echo "PNG转换后无效,删除: $final_png_path"
            rm -f "$final_png_path"
            rm -f "$temp_path"
            exit 1
        fi
        # 转换成功,删除临时文件
        rm -f "$temp_path"
        # echo "成功下载并转换为PNG: $final_png_path"
    else
        echo "转换PNG失败: $temp_path"
        rm -f "$temp_path"
        rm -f "$final_png_path" 2>/dev/null
        exit 1
    fi
else
    if ! magick identify "$final_png_path" &>/dev/null || [ ! -s "$final_png_path" ]; then
        echo "发现无效的PNG文件,重新下载: $url"
        rm -f "$final_png_path"
        # 递归调用自身以重新下载
        $0 "$url"
    else
        echo "PNG文件已存在且有效: $final_png_path"
    fi
fi
EOF
chmod +x "$TMP_DIR/download_worker.sh"
echo "开始下载卡片图片,使用 $THREAD_NUM 个并行进程..."
timeout 3600 bash -c "cat \"$TMP_DIR/image_urls.txt\" | xargs -P $THREAD_NUM -I {} ./\"$TMP_DIR/download_worker.sh\" {}"
download_status=$?
if [ $download_status -eq 124 ]; then
    echo "警告: 下载操作超时（1小时）,部分图片可能未下载完成"
elif [ $download_status -ne 0 ]; then
    echo "警告: 下载过程中出现错误,退出代码 $download_status"
fi
rm -f "$TMP_DIR/image_urls.txt" "$TMP_DIR/download_worker.sh"
DOWNLOADED=$(ls -1 "$TMP_DIR" 2>/dev/null | wc -l)
echo "图片下载完成！成功下载 $DOWNLOADED 张图片到 $TMP_DIR 目录"
if [ $DOWNLOADED -eq 0 ]; then
    echo "警告: 没有成功下载任何图片,请检查网络连接或URL列表"
elif [ $DOWNLOADED -lt $TOTAL ]; then
    echo "提示: 部分图片可能未能下载,成功率: $(($DOWNLOADED * 100 / $TOTAL))%"
fi
echo "所有操作已完成！"
exit 0
