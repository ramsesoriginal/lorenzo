SourceList["T:AC"] = { name : "Test Armour Class Book", abbreviation : "TAC", group : "Homebrew", date : "2026/11/18" };

ArmourList["robe of stillness"] = {
	regExpSearch : /robe of stillness/i,
	name : "Robe of stillness",
	source : [["T:AC", 1]],
	ac : "10+Wis",
	list : "firstlist"
};

ArmourList["turtle shell"] = {
	regExpSearch : /turtle shell/i,
	name : "Turtle shell",
	source : [["T:AC", 2]],
	ac : 17,
	dex : -10,
	list : "firstlist"
};

ArmourList["robe of focus"] = {
	regExpSearch : /robe of focus/i,
	name : "Robe of focus",
	source : [["T:AC", 3]],
	ac : "10+Wis",
	weight : 2
};
