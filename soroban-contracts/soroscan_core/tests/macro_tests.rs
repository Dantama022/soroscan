// Integration tests for the `emit_soroscan_event!` / `emit_soroscan_batch!`
// proc-macros (issue #1667).
//
// The macros must produce the standardized SoroScan topic layout and handle
// every payload shape a contract author might pass:
//
//   * a scalar payload,
//   * a tuple payload (whose inner commas used to break the old
//     string-splitting parser), and
//   * the batch summary form.
//
// `env.events().publish` only records events inside a contract invocation, so
// these tests register a small harness contract whose methods call the macros
// and then inspect the recorded events via `testutils::Events::all`.

use soroban_sdk::testutils::{Address as _, Events as _};
use soroban_sdk::{
    contract, contractimpl, symbol_short, Address, Env, Symbol, TryIntoVal, Val, Vec,
};
use soroscan_macros::{emit_soroscan_batch, emit_soroscan_event};

#[contract]
pub struct MacroHarness;

#[contractimpl]
impl MacroHarness {
    /// Emit with a scalar (`u32`) payload.
    pub fn emit_scalar(env: Env, event_type: Symbol) {
        emit_soroscan_event!(&env, event_type, 42u32);
    }

    /// Emit with a tuple payload. The inner commas must not be mistaken for
    /// argument separators.
    pub fn emit_tuple(env: Env, event_type: Symbol, from: Address, to: Address) {
        emit_soroscan_event!(&env, event_type, (from, to, 7u32));
    }

    /// Emit the batch summary event.
    pub fn emit_batch(env: Env, indexer: Address, count: u32, total: u32) {
        emit_soroscan_batch!(&env, indexer, count, total);
    }
}

fn topic_symbol(env: &Env, topics: &Vec<Val>, index: u32) -> Symbol {
    topics
        .get(index)
        .expect("topic missing")
        .try_into_val(env)
        .expect("topic is not a symbol")
}

#[test]
fn test_emit_scalar_event_topics_and_data() {
    let env = Env::default();
    let contract_id = env.register_contract(None, MacroHarness);
    let client = MacroHarnessClient::new(&env, &contract_id);

    client.emit_scalar(&symbol_short!("swap"));

    let events = env.events().all();
    assert_eq!(events.len(), 1, "should emit exactly one event");

    let (_contract, topics, data) = events.get(0).unwrap();

    // Standard layout: ("soroscan", <event_type>).
    assert_eq!(topics.len(), 2, "scalar event should have two topics");
    assert_eq!(topic_symbol(&env, &topics, 0), symbol_short!("soroscan"));
    assert_eq!(topic_symbol(&env, &topics, 1), symbol_short!("swap"));

    // Data is the scalar payload.
    let value: u32 = data.try_into_val(&env).expect("data should be u32");
    assert_eq!(value, 42);
}

#[test]
fn test_emit_tuple_payload_is_not_split() {
    let env = Env::default();
    let contract_id = env.register_contract(None, MacroHarness);
    let client = MacroHarnessClient::new(&env, &contract_id);

    let from = Address::generate(&env);
    let to = Address::generate(&env);

    client.emit_tuple(&symbol_short!("transfer"), &from, &to);

    let events = env.events().all();
    assert_eq!(events.len(), 1, "should emit exactly one event");

    let (_contract, topics, data) = events.get(0).unwrap();

    // Topics are still the standard pair, despite the payload's commas.
    assert_eq!(topics.len(), 2, "tuple event should have two topics");
    assert_eq!(topic_symbol(&env, &topics, 0), symbol_short!("soroscan"));
    assert_eq!(topic_symbol(&env, &topics, 1), symbol_short!("transfer"));

    // Data is the intact 3-element tuple, encoded as a Vec.
    let parts: Vec<Val> = data
        .try_into_val(&env)
        .expect("tuple data should decode to a vector");
    assert_eq!(
        parts.len(),
        3,
        "tuple payload should keep all three elements"
    );

    let part_from: Address = parts.get(0).unwrap().try_into_val(&env).unwrap();
    let part_to: Address = parts.get(1).unwrap().try_into_val(&env).unwrap();
    let amount: u32 = parts.get(2).unwrap().try_into_val(&env).unwrap();

    assert_eq!(part_from, from);
    assert_eq!(part_to, to);
    assert_eq!(amount, 7);
}

#[test]
fn test_emit_batch_summary_topics_and_data() {
    let env = Env::default();
    let contract_id = env.register_contract(None, MacroHarness);
    let client = MacroHarnessClient::new(&env, &contract_id);

    let indexer = Address::generate(&env);
    client.emit_batch(&indexer, &3u32, &10u32);

    let events = env.events().all();
    assert_eq!(events.len(), 1, "should emit exactly one batch event");

    let (_contract, topics, data) = events.get(0).unwrap();

    // Batch layout: ("soroscan", "batch").
    assert_eq!(topics.len(), 2, "batch event should have two topics");
    assert_eq!(topic_symbol(&env, &topics, 0), symbol_short!("soroscan"));
    assert_eq!(topic_symbol(&env, &topics, 1), symbol_short!("batch"));

    // Data is the (indexer, count, total) tuple.
    let parts: Vec<Val> = data
        .try_into_val(&env)
        .expect("batch data should decode to a vector");
    assert_eq!(parts.len(), 3);

    let part_indexer: Address = parts.get(0).unwrap().try_into_val(&env).unwrap();
    let count: u32 = parts.get(1).unwrap().try_into_val(&env).unwrap();
    let total: u32 = parts.get(2).unwrap().try_into_val(&env).unwrap();

    assert_eq!(part_indexer, indexer);
    assert_eq!(count, 3);
    assert_eq!(total, 10);
}

#[test]
fn test_multiple_emits_accumulate_events() {
    let env = Env::default();
    let contract_id = env.register_contract(None, MacroHarness);
    let client = MacroHarnessClient::new(&env, &contract_id);

    client.emit_scalar(&symbol_short!("mint"));
    client.emit_scalar(&symbol_short!("burn"));

    let events = env.events().all();
    assert_eq!(events.len(), 2, "each emit should record its own event");

    let (_, first_topics, _) = events.get(0).unwrap();
    let (_, second_topics, _) = events.get(1).unwrap();
    assert_eq!(topic_symbol(&env, &first_topics, 1), symbol_short!("mint"));
    assert_eq!(topic_symbol(&env, &second_topics, 1), symbol_short!("burn"));
}

#[test]
fn test_emit_soroscan_event_macro_with_tuple_payload_publishes_one_event() {
    // Regression test for #1649: a payload containing commas (a tuple) used
    // to be naively split, which expanded to malformed code. The macro must
    // accept it as a single argument and publish exactly one event.
    let env = Env::default();
    let contract_id = env.register_contract(None, MacroHarness);

    let sender: u32 = 1;
    let receiver: u32 = 2;
    let amount: i128 = 3;

    env.as_contract(&contract_id, || {
        emit_soroscan_event!(env, symbol_short!("swap"), (sender, receiver, amount));
    });

    assert_eq!(
        env.events().all().len(),
        1,
        "tuple payload should emit exactly one event"
    );
}

#[test]
fn test_emit_soroscan_batch_macro_with_tuple_argument_publishes_one_event() {
    // Regression test for #1649: the same comma-splitting bug affected
    // emit_soroscan_batch!. An argument containing a comma (here a tuple)
    // must be accepted intact.
    let env = Env::default();
    let contract_id = env.register_contract(None, MacroHarness);
    let indexer = Address::generate(&env);

    env.as_contract(&contract_id, || {
        emit_soroscan_batch!(env, indexer, (5u32, 6u32), 42u32);
    });

    assert_eq!(env.events().all().len(), 1);
}
