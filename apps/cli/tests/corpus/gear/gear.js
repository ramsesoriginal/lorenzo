GearList["purple lamp"] = {
	infoname : "Purple lamp [5 gp]",
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
	infoname : "Purplemancer's tools [500 gp]",
	type : "artisan's tools",
	weight : 8
};

AmmoList["purple arrow"] = {
	name : "Purple arrows",
	weight : 0.05,
	icon : "Arrows",
	invName : "Arrows, purple",
	alternatives : ["arrows, purple", "violet arrows", /purple\s+arrows?/i]
};

PacksList["purple pack"] = {
	name : "Purple pack (10 gp)",
	source : [["HB", 0]],
	items : [
		["Backpack, with:", "", 5],
		["Rations, days of", 5, 2],
		["Tinderbox", "", 1],
		["Waterskin", "", 5],
		["Hempen rope, feet of", 50, 0.2]
	]
};
