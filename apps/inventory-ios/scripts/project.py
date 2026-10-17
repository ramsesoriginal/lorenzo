"""Deterministic, dependency-free Xcode project for the app and native UI tests."""
from pathlib import Path
import hashlib, plistlib, json
root = Path(__file__).resolve().parent.parent
def ident(name): return hashlib.sha1(name.encode()).hexdigest()[:24].upper()
objects = {}
def obj(key, **value):
    i = ident(key); objects[i] = value; return i
appfiles = sorted(root.glob("Sources/**/*.swift"))
resources = sorted((root / "Resources").glob("*"))
ui = sorted(root.glob("UITests/*.swift"))
def phase(name, paths, isa):
    builds=[]
    for p in paths:
        ref=obj(str(p.relative_to(root)),isa="PBXFileReference",path=str(p.relative_to(root)),sourceTree="<group>")
        builds.append(obj("build"+str(p.relative_to(root)),isa="PBXBuildFile",fileRef=ref))
    return obj(name,isa=isa,buildActionMask=2147483647,files=builds,runOnlyForDeploymentPostprocessing=0)
sources=phase("sources",appfiles,"PBXSourcesBuildPhase")
res=phase("resources",resources,"PBXResourcesBuildPhase")
tests=phase("tests",ui,"PBXSourcesBuildPhase")
appProduct=obj("appProduct",isa="PBXFileReference",explicitFileType="wrapper.application",path="LorenzoInventory.app",sourceTree="BUILT_PRODUCTS_DIR")
uiProduct=obj("uiProduct",isa="PBXFileReference",explicitFileType="wrapper.cfbundle",path="InventoryUITests.xctest",sourceTree="BUILT_PRODUCTS_DIR")
group=obj("mainGroup",isa="PBXGroup",children=[ident(str(p.relative_to(root))) for p in appfiles+resources+ui]+[appProduct,uiProduct],sourceTree="<group>")
def configs(name, extra):
    common={"SWIFT_VERSION":"5.0","IPHONEOS_DEPLOYMENT_TARGET":"17.0","SDKROOT":"iphoneos","SUPPORTED_PLATFORMS":"iphoneos iphonesimulator","TARGETED_DEVICE_FAMILY":"1,2","CODE_SIGN_STYLE":"Automatic","GENERATE_INFOPLIST_FILE":"YES","CLANG_ENABLE_MODULES":"YES","SWIFT_EMIT_LOC_STRINGS":"NO"}
    common.update(extra)
    cs=[obj(name+c,isa="XCBuildConfiguration",name=c,buildSettings={**common,"SWIFT_OPTIMIZATION_LEVEL":"-Onone" if c=="Debug" else "-O"}) for c in ["Debug","Release"]]
    return obj(name+"list",isa="XCConfigurationList",buildConfigurations=cs,defaultConfigurationIsVisible=0,defaultConfigurationName="Release")
version=(root/"version.txt").read_text().strip()
appconfig=configs("app",{"PRODUCT_BUNDLE_IDENTIFIER":"io.lorenzo.inventory.ios","PRODUCT_NAME":"LorenzoInventory","MARKETING_VERSION":version,"CURRENT_PROJECT_VERSION":"1","ASSETCATALOG_COMPILER_APPICON_NAME":"AppIcon","INFOPLIST_FILE":"Info.plist","GENERATE_INFOPLIST_FILE":"NO"})
app=obj("app",isa="PBXNativeTarget",name="LorenzoInventory",productName="LorenzoInventory",productReference=appProduct,productType="com.apple.product-type.application",buildConfigurationList=appconfig,buildPhases=[sources,res],buildRules=[],dependencies=[])
proxy=obj("proxy",isa="PBXContainerItemProxy",containerPortal=ident("project"),proxyType=1,remoteGlobalIDString=app,remoteInfo="LorenzoInventory")
dep=obj("dependency",isa="PBXTargetDependency",target=app,targetProxy=proxy)
testconfig=configs("ui",{"PRODUCT_BUNDLE_IDENTIFIER":"io.lorenzo.inventory.ios.tests","PRODUCT_NAME":"InventoryUITests","TEST_TARGET_NAME":"LorenzoInventory"})
test=obj("ui",isa="PBXNativeTarget",name="InventoryUITests",productName="InventoryUITests",productReference=uiProduct,productType="com.apple.product-type.bundle.ui-testing",buildConfigurationList=testconfig,buildPhases=[tests],buildRules=[],dependencies=[dep])
project=obj("project",isa="PBXProject",attributes={"LastUpgradeCheck":"1600"},buildConfigurationList=configs("project",{}),compatibilityVersion="Xcode 14.0",developmentRegion="en",hasScannedForEncodings=0,knownRegions=["en","Base"],mainGroup=group,projectDirPath="",projectRoot="",targets=[app,test])
dest=root/"LorenzoInventory.xcodeproj"; dest.mkdir(exist_ok=True)
# Xcode accepts XML plist project files; avoid an OpenStep serializer dependency.
(dest/"project.pbxproj").write_bytes(plistlib.dumps({"archiveVersion":"1","classes":{},"objectVersion":"56","objects":objects,"rootObject":project},fmt=plistlib.FMT_XML,sort_keys=True))
scheme=dest/"xcshareddata/xcschemes"; scheme.mkdir(parents=True,exist_ok=True)
def ref(i,name): return f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{i}" BuildableName="{name}" BlueprintName="{name.split(".")[0]}" ReferencedContainer="container:LorenzoInventory.xcodeproj"/>'
(scheme/"LorenzoInventory.xcscheme").write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1600" version="1.3"><BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">{ref(app,"LorenzoInventory.app")}</BuildActionEntry></BuildActionEntries></BuildAction><TestAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv="YES"><Testables><TestableReference skipped="NO">{ref(test,"InventoryUITests.xctest")}</TestableReference></Testables></TestAction><LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" debugServiceExtension="internal" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0">{ref(app,"LorenzoInventory.app")}</BuildableProductRunnable></LaunchAction></Scheme>
''')
print(dest)
