set -eu
cd "$(dirname "$0")/.."
if [ "$(uname)" != Darwin ]; then
  echo "Native iOS checks require Xcode on macOS (the public CI runner supplies it)." >&2
  exit 1
fi
swift scripts/icon.swift
python3 scripts/project.py
case "$1" in
 lint) swiftc -parse Sources/Core/*.swift Sources/App/*.swift
       python3 -m unittest discover -s scripts -p 'test_*.py' ;;
 test)
   swift test
   python3 scripts/ui_server.py > build-ui-server.log 2>&1 &
   fixture_pid=$!
   trap 'kill "$fixture_pid" 2>/dev/null || true' EXIT
   bash scripts/run.sh ui-test
   ;;
 build)
   xcodebuild -project LorenzoInventory.xcodeproj -scheme LorenzoInventory -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' -derivedDataPath build/device CODE_SIGNING_ALLOWED=NO build > build-device.log 2>&1 || { tail -n 100 build-device.log; exit 1; }
   mkdir -p build/ipa/Payload
   ditto build/device/Build/Products/Release-iphoneos/LorenzoInventory.app build/ipa/Payload/LorenzoInventory.app
   (cd build/ipa && zip -qry ../Lorenzo-Inventory.ipa Payload)
   ;;
 ui-test)
   destination=$(xcrun simctl list devices available -j | python3 -c 'import json,sys; d=json.load(sys.stdin); print(next(x["udid"] for a in d["devices"].values() for x in a if x["name"].startswith("iPhone")))')
   xcodebuild -project LorenzoInventory.xcodeproj -scheme LorenzoInventory -destination "platform=iOS Simulator,id=$destination" -derivedDataPath build/simulator -resultBundlePath build/UITests.xcresult CODE_SIGNING_ALLOWED=NO test > build-uitest.log 2>&1 || { tail -n 120 build-uitest.log; exit 1; }
   ;;
 dev)
   echo "Open LorenzoInventory.xcodeproj in Xcode, select a simulator and Run." ;;
 *) exit 2 ;;
esac
