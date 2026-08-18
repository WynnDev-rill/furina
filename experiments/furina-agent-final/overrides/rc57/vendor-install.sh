#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail
ROOT="${FURINA_ROOT:-$HOME/.furina-agent}"
LOCK="${1:-$(dirname "$0")/upstreams.lock.json}"
DEST="$ROOT/upstreams"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST" "$DEST/.locks"
command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null
command -v tar >/dev/null 2>&1 || pkg install -y tar >/dev/null

python - "$LOCK" <<'PY' > "$TMP/sources.tsv"
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
for s in m['sources']:
    print('\t'.join([s['id'],s['repo'],s['ref'],s['license'],s['integration'],s['archive'],'|'.join(s['required'])]))
PY

while IFS=$'\t' read -r id repo ref license mode archive required; do
  target="$DEST/$id/$ref"
  marker="$DEST/.locks/$id.json"
  if [[ -f "$marker" && -d "$target" ]] && python - "$marker" "$ref" <<'PY' >/dev/null 2>&1
import json,sys
m=json.load(open(sys.argv[1])); raise SystemExit(0 if m.get('ref')==sys.argv[2] and m.get('complete') else 1)
PY
  then
    printf 'UPSTREAM %s already pinned at %s\n' "$id" "${ref:0:12}"
    continue
  fi

  archive_file="$TMP/$id.tar.gz"
  stage="$TMP/$id-stage"
  rm -rf "$stage" "$archive_file"
  mkdir -p "$stage"
  printf 'UPSTREAM %s downloading full source...\n' "$id"
  curl -fL --silent --show-error --connect-timeout 15 --max-time 600 --retry 3 --retry-delay 2 --retry-all-errors "$archive" -o "$archive_file"
  tar -xzf "$archive_file" -C "$stage" --strip-components=1

  IFS='|' read -ra reqs <<< "$required"
  for rel in "${reqs[@]}"; do
    [[ -e "$stage/$rel" ]] || { echo "Upstream $id incomplete: missing $rel" >&2; exit 1; }
  done

  mkdir -p "$(dirname "$target")"
  new="$target.new"
  rm -rf "$new"
  mv "$stage" "$new"
  rm -rf "$target"
  mv "$new" "$target"

  python - "$marker" "$id" "$repo" "$ref" "$license" "$mode" <<'PY'
import json,sys,time,os
p,id_,repo,ref,lic,mode=sys.argv[1:]
os.makedirs(os.path.dirname(p),exist_ok=True)
tmp=p+'.new'
json.dump({'id':id_,'repo':repo,'ref':ref,'license':lic,'integration':mode,'complete':True,'installed_at':time.time()},open(tmp,'w'),indent=2)
os.replace(tmp,p)
PY
  printf 'UPSTREAM %s installed (%s, %s)\n' "$id" "$license" "${ref:0:12}"
done < "$TMP/sources.tsv"

printf 'FURINA_UPSTREAM_VENDOR_OK\n'
