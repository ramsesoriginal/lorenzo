// Patches an entry in place: it stays the base file's entry, with a heavier weight.
WeaponsList["longsword"].weight = 4;

// Replaces an entry outright: it is now this file's.
WeaponsList["dagger"] = {
	regExpSearch : /dagger/i,
	name : "Dagger",
	source : ["HB", 0],
	list : "melee",
	type : "Simple",
	damage : [1, 4, "piercing"],
	range : "Melee, 20/60 ft",
	weight : 0.5
};

// Adds a new one.
WeaponsList["glass sword"] = { name : "Glass sword", source : ["HB", 0], type : "Martial", list : "melee", weight : 2 };

// Removes one.
delete ArmourList["padded"];
