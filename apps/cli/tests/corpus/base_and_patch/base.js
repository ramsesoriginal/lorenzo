var Base_SourceList = {
	"P" : { name : "Player's Handbook", abbreviation : "PHB", group : "Primary", date : "2014/08/19" }
};

var Base_WeaponsList = {
	"longsword" : {
		regExpSearch : /^(?=.*long)(?=.*sword).*$/i,
		name : "Longsword",
		source : [["SRD", 66], ["P", 149]],
		list : "melee",
		type : "Martial",
		damage : [1, 8, "slashing"],
		range : "Melee",
		weight : 3
	},
	"dagger" : {
		regExpSearch : /dagger/i,
		name : "Dagger",
		source : [["SRD", 65], ["P", 148]],
		list : "melee",
		type : "Simple",
		damage : [1, 4, "piercing"],
		range : "Melee, 20/60 ft",
		weight : 1
	}
};

var Base_ArmourList = {
	"padded" : { name : "Padded", type : "light", ac : 11, weight : 8 }
};
