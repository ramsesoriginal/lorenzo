GearList["backpack"] = {
	infoname : "Backpack [2 gp]",
	name : "Backpack",
	amount : "",
	weight : 5
};

GearList["rations (1 day)"] = {
	infoname : "Rations (1 day) [5 sp]",
	name : "Rations, days of",
	amount : 1,
	weight : 2
};

GearList["torch"] = {
	infoname : "Torch [1 cp]",
	name : "Torch",
	amount : "",
	weight : 1
};

GearList["rope, hempen (50 feet)"] = {
	infoname : "Rope, hempen (50 feet) [1 gp]",
	name : "Hempen rope, feet of",
	amount : 50,
	weight : 0.2
};

PacksList["camper"] = {
	name : "Camper's pack (7 gp)",
	source : [["HB", 0]],
	items : [
		["Backpack, with:", "", 5],
		["Rations, days of", 5, 2],
		["Torches", 2, 1],
		["Hempen rope, feet of", 50, 0.2],
		["Alms box", "", ""],
		["Mystery thing", "", ""]
	]
};
