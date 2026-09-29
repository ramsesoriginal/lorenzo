ArmourList["purple plate"] = {
	regExpSearch : /purple plate/i,
	name : "Purple plate",
	source : [["HB", 0]],
	type : "heavy",
	ac : 18,
	stealthdis : true,
	weight : 60,
	strReq : 15
};

ArmourList["violet robe"] = {
	regExpSearch : /violet robe/i,
	name : "Violet robe",
	source : [["HB", 0]],
	ac : "10+Wis",
	addMod : true,
	weight : 4
};

GearList["backpack"] = {
	infoname : "Backpack [2 gp]",
	name : "Backpack",
	amount : "",
	weight : 5
};

GearList["purple lamp"] = {
	infoname : "Purple lamp [5 gp 5 sp]",
	name : "Purple lamp",
	amount : "",
	weight : 1,
	type : "equipment"
};

GearList["violet bullets"] = {
	infoname : "Bullets, Violet (10) [5 sp]",
	name : "Bullets, Violet",
	amount : 10,
	weight : 0.05,
	type : "ammunition"
};

ToolsList["purplemancer's tools"] = {
	name : "Purplemancer's tools",
	infoname : "Purplemancer's tools [1,500 gp]",
	amount : "",
	type : "artisan's tools",
	weight : 8
};

AmmoList["purple arrow"] = {
	name : "Purple arrows",
	weight : 0.05,
	icon : "Arrows",
	invName : "Arrows, purple",
	alternatives : ["arrows, purple", /purple\s+arrows?/i]
};

PacksList["purple pack"] = {
	name : "Purple pack (10 gp)",
	source : [["HB", 0]],
	items : [["Backpack, with:", "", 5], ["Rations, days of", 5, 2]]
};
