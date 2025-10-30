#!/usr/bin/env bash
set -euo pipefail

cd /var/www/sitefixer/frontend

OUT=/tmp/frontend-inventory
mkdir -p "$OUT"

# 1) Baumstruktur
if command -v tree >/dev/null 2>&1; then
  tree -a -I 'node_modules|dist|.git' > "$OUT/tree.txt"
else
  find . -path './node_modules' -prune -o -path './dist' -prune -o -print \
    | sed 's|^\./||' \
    | awk -F'/' '{
        indent=""; for(i=1;i<NF;i++) indent=indent "  ";
        print indent $NF
      }' > "$OUT/tree.txt"
fi

# 2) Detailliste
find . \
  -path './node_modules' -prune -o -path './dist' -prune -o \
  -printf '%M %6s %TY-%Tm-%Td %TH:%TM  %p\n' \
  | sed 's|^\./||' | sort > "$OUT/ls.txt"

# 3) Header einiger Schlüsseldateien
printf "%s\n" \
  src/main.ts \
  src/App.vue \
  src/router.ts \
  src/api.ts \
  src/layouts/Layout.vue \
  src/components/Sidebar.vue \
  src/components/Topbar.vue \
  src/pages/Dashboard.vue \
  src/pages/Users.vue \
  src/pages/Settings.vue \
  src/pages/TicketDetail.vue \
  | while read -r f; do
      if [ -f "$f" ]; then
        echo "----- $f" >> "$OUT/head.txt"
        sed -n '1,60p' "$f" >> "$OUT/head.txt"
        echo >> "$OUT/head.txt"
      fi
    done

echo "✔ Inventar erstellt:"
echo "  - $OUT/tree.txt"
echo "  - $OUT/ls.txt"
echo "  - $OUT/head.txt"
