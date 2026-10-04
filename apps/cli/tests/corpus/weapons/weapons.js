var iFileName = "weapons.js";
RequiredSheetVersion("14.0.5", "24.0.0");

SourceList["T:W"] = {
	name : "Test Weapons Book",
	abbreviation : "TWB",
	group : "Homebrew",
	date : "2026/01/02"
};

WeaponsList["purple sword"] = {
	regExpSearch : /^(?=.*sword)(?=.*purple).*$/i,
	name : "Purple sword",
	source : ["HB", 0],
	source : [["T:W", 4], ["P", 149]],
	type : "Martial",
	list : "melee",
	ability : 1,
	abilitytodamage : true,
	damage : [1, 8, "slashing"],
	range : "Melee",
	weight : 3,
	description : "Versatile (1d10)",
	alternatives : ["violet sword", /lilac\s+blade/i],
	calcChanges : {
		atkAdd : [
			function (fields, v) {
				fields.Description += "; Never runs";
			},
			"Adds a note"
		]
	}
};

WeaponsList["purple bow"] = {
	regExpSearch : /purple.*bow/i,
	name : "Purple bow",
	source : [["T:W", 5]],
	type : "Martial",
	list : "ranged",
	ability : 2,
	damage : [1, 8, "piercing"],
	range : "150/600 ft",
	weight : 2,
	description : "Ammunition, heavy, two-handed"
};

WeaponsList["purple dart"] = {
	regExpSearch : /purple dart/i,
	name : "Purple dart",
	source : [["T:W", 6]],
	type : "Simple",
	ability : 2,
	damage : [1, 4, "piercing"],
	range : "Melee, 20/60 ft",
	weight : 0.25,
	description : "Finesse, thrown"
};

WeaponsList["purple glare"] = {
	regExpSearch : /purple glare/i,
	name : "Purple glare",
	source : [["T:W", 7]],
	type : "Cantrip",
	list : "spell",
	ability : 6,
	damage : ["C", 10, "radiant"],
	range : "60 ft"
};

WeaponsList["moon whip"] = {
	regExpSearch : /moon whip/i,
	name : "Moon whip",
	source : ["HB", 0],
	type : "Exotic",
	list : "melee",
	ability : 2,
	damage : [1, 6, "slashing"],
	range : "Melee",
	weight : 2
};
