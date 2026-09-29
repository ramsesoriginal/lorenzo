var metric = What("Unit System") === "metric";
var chained = Value("Field").deeper.deepest("x");
tDoc.someProperty = 1;

WeaponsList["plain"] = {
	name : "Plain",
	source : ["HB", 0],
	type : "Simple",
	list : "melee",
	weight : metric ? 1 : 2,
	unknown : What("Level"),
	fromChain : chained
};

WeaponsList["later"] = { name : "Later", source : ["HB", 0], type : "Simple", list : "melee", weight : 1 };
