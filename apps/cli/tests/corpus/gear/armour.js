ArmourList["purple plate"] = {
	regExpSearch : /^(?=.*purple)(?=.*plate).*$/i,
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
	ac : 12,
	ac : "10+Wis",
	addMod : true,
	weight : 4
};

ArmourList["tower shield"] = {
	regExpSearch : /tower shield/i,
	name : "Tower shield",
	source : [["HB", 0]],
	type : "",
	ac : 3,
	weight : 20
};
