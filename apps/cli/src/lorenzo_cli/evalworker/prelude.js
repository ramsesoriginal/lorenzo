// The runtime surface MPMB's "additional content syntax" files assume (RFC 0025 R1, ADR 0138).
//
// Evaluated once in a fresh V8 context before the source files. Nothing here can reach the
// network or the disk: V8 has no I/O of its own, and this file adds none.
//
// It does four things:
//   1. seeds the plain objects the files assign into (`WeaponsList["longsword"] = {...}`);
//   2. neutralises Math.random and Date, so a run is a pure function of its input;
//   3. provides a recording stub for names the sheet supplies and this host does not
//      (`What(...)`, `Value(...)`, `app`...), which absorbs any call, property read or `new`;
//   4. serialises results to tagged JSON: a RegExp becomes {"$re": [source, flags]}, a function
//      becomes {"$fn": text} and is never called.
var __lorenzo = (function (global) {
  var STUB = Symbol.for("lorenzo.stub");
  var stubCalls = Object.create(null);
  var stubFirstFile = Object.create(null);
  var stubsInData = [];
  var state = { file: "" };

  // Lists the files assign into. A list a run doesn't ask for is still seeded, so a file that
  // defines feats or spells can be evaluated without a ReferenceError, and counted.
  var LIST_NAMES = [
    "WeaponsList", "ArmourList", "GearList", "PacksList", "ToolsList", "AmmoList", "SourceList",
    "FeatsList", "MagicItemsList", "SpellsList", "ClassList", "ClassSubList", "RaceList",
    "RaceSubList", "BackgroundList", "BackgroundSubList", "BackgroundFeatureList",
    "CreatureList", "CompanionList", "PsionicsList", "SpellListsList",
  ];
  LIST_NAMES.forEach(function (name) { global[name] = {}; });

  // Which file each list entry came from. An entry belongs to the file that last put a new
  // object under its key; a file that patches an entry in place (`WeaponsList["x"].y = 1`)
  // doesn't take it over. `known` holds the object last seen under each key.
  var known = Object.create(null);
  var origins = Object.create(null);

  function cloneDeep(value) {
    if (value instanceof RegExp) return new RegExp(value.source, value.flags);
    if (Array.isArray(value)) return value.map(cloneDeep);
    if (value !== null && typeof value === "object") {
      var out = {};
      Object.keys(value).forEach(function (key) { out[key] = cloneDeep(value[key]); });
      return out;
    }
    return value; // primitives, and functions (never called, so sharing them is harmless)
  }

  // After a file ran, note which entries of each list are new or replaced, and which are gone.
  // `prefix` is "Base_" while the sheet's base data is being defined, "" afterwards.
  function noteOrigins(prefix, file) {
    LIST_NAMES.forEach(function (name) {
      var listName = prefix + name;
      var list = global[listName];
      if (list === null || typeof list !== "object") return;
      var seen = known[listName] || (known[listName] = Object.create(null));
      var from = origins[listName] || (origins[listName] = Object.create(null));
      Object.keys(list).forEach(function (key) {
        if (!(key in seen) || seen[key] !== list[key]) {
          seen[key] = list[key];
          from[key] = file;
        }
      });
      Object.keys(seen).forEach(function (key) {
        if (!Object.prototype.hasOwnProperty.call(list, key)) {
          delete seen[key];
          delete from[key];
        }
      });
    });
  }

  // What the sheet's InitiateLists() does before it runs any user script: every list becomes a
  // copy of its Base_ list (the SRD data), or an empty one. Homebrew files are written against
  // lists that already hold the SRD, and some patch its entries.
  function initiateLists() {
    LIST_NAMES.forEach(function (name) {
      var base = global["Base_" + name];
      global[name] = base !== null && typeof base === "object" ? cloneDeep(base) : {};
      var seen = (known[name] = Object.create(null));
      var from = (origins[name] = Object.create(null));
      var baseFrom = origins["Base_" + name] || Object.create(null);
      Object.keys(global[name]).forEach(function (key) {
        seen[key] = global[name][key];
        from[key] = baseFrom[key] || "";
      });
    });
  }

  // Determinism: no clock, no randomness.
  Math.random = function () { return 0.5; };
  var RealDate = Date;
  var FixedDate = function () {
    var args = Array.prototype.slice.call(arguments);
    if (!(this instanceof FixedDate)) return new RealDate(0).toString();
    return args.length ? new (Function.prototype.bind.apply(RealDate, [null].concat(args)))() : new RealDate(0);
  };
  FixedDate.prototype = RealDate.prototype;
  FixedDate.now = function () { return 0; };
  FixedDate.UTC = RealDate.UTC;
  FixedDate.parse = RealDate.parse;
  global.Date = FixedDate;

  function called(name) {
    stubCalls[name] = (stubCalls[name] || 0) + 1;
    if (!(name in stubFirstFile)) stubFirstFile[name] = state.file;
  }

  function makeStub(name) {
    var proxy;
    var handler = {
      get: function (target, prop) {
        if (prop === STUB) return name;
        if (prop === Symbol.toPrimitive) return function () { return 0; };
        if (prop === "then") return undefined; // not a thenable
        return proxy;
      },
      apply: function () { called(name); return proxy; },
      construct: function () { called(name); return proxy; },
      set: function () { return true; },
      has: function () { return true; },
      deleteProperty: function () { return true; },
    };
    proxy = new Proxy(function () {}, handler);
    return proxy;
  }

  function seedStubs(names) {
    names.forEach(function (name) {
      if (!(name in global)) {
        global[name] = makeStub(name);
        stubCalls[name] = stubCalls[name] || 0;
      }
    });
  }

  function setFile(name) {
    state.file = name;
  }

  // The sheet's own version guard; nothing to check here.
  global.RequiredSheetVersion = function () {};

  var MAX_DEPTH = 60;

  function serialise(value, path, ancestors) {
    switch (typeof value) {
      case "string":
      case "boolean":
        return value;
      case "number":
        return isFinite(value) ? value : { "$num": String(value) };
      case "undefined":
        return null;
      case "symbol":
      case "bigint":
        return { "$unsupported": typeof value };
      case "function": {
        var stubName = value[STUB];
        if (stubName !== undefined) {
          if (stubsInData.length < 200) stubsInData.push({ path: path, stub: stubName });
          return { "$stub": stubName };
        }
        return { "$fn": Function.prototype.toString.call(value) };
      }
    }
    if (value === null) return null;
    if (value instanceof RegExp) return { "$re": [value.source, value.flags] };
    if (value instanceof RealDate) return { "$date": value.getTime() };
    if (ancestors.indexOf(value) !== -1) return { "$cycle": true };
    if (ancestors.length >= MAX_DEPTH) return { "$deep": true };
    ancestors.push(value);
    var out;
    if (Array.isArray(value)) {
      out = value.map(function (item, i) { return serialise(item, path + "[" + i + "]", ancestors); });
    } else {
      out = {};
      Object.keys(value).forEach(function (key) {
        var item;
        try { item = value[key]; } catch (e) { out[key] = { "$error": String(e) }; return; }
        if (item === undefined) return; // like JSON: an undefined property is absent
        out[key] = serialise(item, path + "." + key, ancestors);
      });
    }
    ancestors.pop();
    return out;
  }

  function snapshot(listNames) {
    var lists = {};
    listNames.forEach(function (name) {
      lists[name] = serialise(global[name], name, []);
    });
    var counts = {};
    LIST_NAMES.forEach(function (name) { counts[name] = Object.keys(global[name]).length; });
    var fromFile = {};
    listNames.forEach(function (name) {
      var from = origins[name] || {};
      fromFile[name] = {};
      Object.keys(global[name]).forEach(function (key) { fromFile[name][key] = from[key] || ""; });
    });
    var stubs = Object.keys(stubCalls).sort().map(function (name) {
      return { name: name, calls: stubCalls[name], first_file: stubFirstFile[name] || "" };
    });
    return JSON.stringify({
      lists: lists, origins: fromFile, counts: counts, stubs: stubs, stubs_in_data: stubsInData,
    });
  }

  return {
    seedStubs: seedStubs,
    setFile: setFile,
    noteOrigins: noteOrigins,
    initiateLists: initiateLists,
    snapshot: snapshot,
  };
})(this);
