#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Generate the native vector from the same checked-in SVG as the web build.
dest=app/src/main/res/drawable-nodpi
mkdir -p "$dest"
rm -f "$dest/brand_icon.png"
python3 - "$dest/brand_icon.xml" <<'PY'
import re
import sys
import xml.etree.ElementTree as ET
root=ET.parse("../web/frontend/src/dz-mark.svg").getroot()
ns="{http://www.w3.org/2000/svg}"
assert root.get("viewBox")=="0 0 64 64"
color=root.get("fill","")
assert re.fullmatch(r"#[0-9a-fA-F]{6}",color)
paths=root.findall(ns+"path")
assert len(paths)==2
android="http://schemas.android.com/apk/res/android"
ET.register_namespace("android",android)
def attrs(**values):
    return {"{"+android+"}"+key:value for key,value in values.items()}
vector=ET.Element("vector",attrs(width="64dp",height="64dp",viewportWidth="64",viewportHeight="64"))
for path in paths:
    data=path.get("d","")
    assert re.fullmatch(r"[MLZ0-9. -]+",data)
    ET.SubElement(vector,"path",attrs(fillColor=color,fillType="evenOdd",pathData=data))
ET.ElementTree(vector).write(sys.argv[1],encoding="utf-8",xml_declaration=True)
PY
