var loop = { name : "loop" };
loop.self = loop;

WeaponsList["odd"] = {
	name : "Odd",
	source : ["HB", 0],
	type : "Simple",
	list : "melee",
	notANumber : NaN,
	endless : Infinity,
	when : new Date(86400000),
	gone : undefined,
	nested : [[/a+/g, "text"], { deeper : /b$/im }],
	loop : loop,
	get broken() { throw new Error("nope"); },
	randomness : Math.random(),
	clock : Date.now()
};
