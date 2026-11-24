import { matchesFilters, parseSearchQuery, type SearchFilters } from '@/lib/search-parser';

describe('parseSearchQuery', () => {
  it.each<{ name: string; query: string; expected: SearchFilters }>([
    {
      name: 'empty string',
      query: '',
      expected: { text: [] },
    },
    {
      name: 'whitespace only',
      query: '   \t\n  ',
      expected: { text: [] },
    },
    {
      name: 'single free-text term',
      query: 'stellar',
      expected: { text: ['stellar'] },
    },
    {
      name: 'multiple free-text terms with extra whitespace',
      query: '  stellar   soroban   pool  ',
      expected: { text: ['stellar', 'soroban', 'pool'] },
    },
    {
      name: 'type filter alone',
      query: 'type:transfer',
      expected: { type: 'transfer', text: [] },
    },
    {
      name: 'contract filter alone',
      query: 'contract:CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
      expected: {
        contract: 'CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
        text: [],
      },
    },
    {
      name: 'amount filter with > operator',
      query: 'amount:>1000',
      expected: { amount: { operator: '>', value: 1000 }, text: [] },
    },
    {
      name: 'amount filter with < operator',
      query: 'amount:<250.5',
      expected: { amount: { operator: '<', value: 250.5 }, text: [] },
    },
    {
      name: 'amount filter with >= operator',
      query: 'amount:>=500',
      expected: { amount: { operator: '>=', value: 500 }, text: [] },
    },
    {
      name: 'amount filter with <= operator',
      query: 'amount:<=99',
      expected: { amount: { operator: '<=', value: 99 }, text: [] },
    },
    {
      name: 'amount filter with = operator',
      query: 'amount:=42',
      expected: { amount: { operator: '=', value: 42 }, text: [] },
    },
    {
      name: 'amount filter without explicit operator defaults to =',
      query: 'amount:42',
      expected: { amount: { operator: '=', value: 42 }, text: [] },
    },
    {
      name: 'amount filter with == normalizes to =',
      query: 'amount:==42',
      expected: { amount: { operator: '=', value: 42 }, text: [] },
    },
    {
      name: 'multiple filters combined with interleaved free text',
      query: 'alpha type:swap middle contract:C123 amount:>=100 omega',
      expected: {
        type: 'swap',
        contract: 'C123',
        amount: { operator: '>=', value: 100 },
        text: ['alpha', 'middle', 'omega'],
      },
    },
    {
      name: 'uppercase and mixed-case filter keys normalize to lowercase',
      query: 'TYPE:Swap Contract:CXYZ AMOUNT:>10',
      expected: {
        type: 'Swap',
        contract: 'CXYZ',
        amount: { operator: '>', value: 10 },
        text: [],
      },
    },
    {
      name: 'unknown filter keys are preserved in free text',
      query: 'status:active foo:bar type:mint',
      expected: {
        type: 'mint',
        text: ['status:active', 'foo:bar'],
      },
    },
    {
      name: 'quoted single-token filter value preserves quotes literally',
      query: 'type:"swap"',
      expected: {
        type: '"swap"',
        text: [],
      },
    },
    {
      name: 'quoted multi-word text splits on whitespace',
      query: '"hello world"',
      expected: {
        text: ['"hello', 'world"'],
      },
    },
    {
      name: 'quoted filter value with space captures first token and pushes remainder to text',
      query: 'type:"token transfer"',
      expected: {
        type: '"token',
        text: ['transfer"'],
      },
    },
    {
      name: 'empty filter values fall back to free text',
      query: 'type: contract: amount:',
      expected: {
        text: ['type:', 'contract:', 'amount:'],
      },
    },
    {
      name: 'non-numeric amount value is ignored without adding text',
      query: 'amount:abc type:swap',
      expected: {
        type: 'swap',
        text: [],
      },
    },
    {
      name: 'leading colon without key is treated as free text',
      query: ':orphan',
      expected: {
        text: [':orphan'],
      },
    },
    {
      name: 'repeated known filter keeps the last occurrence',
      query: 'type:swap type:deposit',
      expected: {
        type: 'deposit',
        text: [],
      },
    },
  ])('$name', ({ query, expected }) => {
    expect(parseSearchQuery(query)).toEqual(expected);
  });
});

describe('matchesFilters', () => {
  const baseEvent = {
    eventType: 'TokenTransfer',
    contractId: 'CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    payload: {
      amount: 500,
      from: 'GAAAA',
      to: 'GBBBB',
      memo: 'Liquidity Pool Deposit',
    },
  };

  it('matches any event when filters are empty', () => {
    expect(matchesFilters(baseEvent, { text: [] })).toBe(true);
    expect(
      matchesFilters({ eventType: 'swap', contractId: 'C1' }, { text: [] }),
    ).toBe(true);
  });

  it('matches when all supplied filters match', () => {
    const filters = parseSearchQuery(
      'type:transfer contract:CAAAA amount:>=500 liquidity',
    );
    expect(matchesFilters(baseEvent, filters)).toBe(true);
  });

  it('matches type and contract case-insensitively as substrings', () => {
    expect(
      matchesFilters(baseEvent, { type: 'tokentrans', contract: 'caaaa', text: [] }),
    ).toBe(true);
  });

  it('rejects when type does not match', () => {
    expect(matchesFilters(baseEvent, { type: 'swap', text: [] })).toBe(false);
  });

  it('rejects when contract does not match', () => {
    expect(matchesFilters(baseEvent, { contract: 'CBBBB', text: [] })).toBe(false);
  });

  it.each<{
    operator: '>' | '<' | '>=' | '<=' | '=';
    value: number;
    expected: boolean;
  }>([
    { operator: '>', value: 499, expected: true },
    { operator: '>', value: 500, expected: false },
    { operator: '<', value: 501, expected: true },
    { operator: '<', value: 500, expected: false },
    { operator: '>=', value: 500, expected: true },
    { operator: '>=', value: 501, expected: false },
    { operator: '<=', value: 500, expected: true },
    { operator: '<=', value: 499, expected: false },
    { operator: '=', value: 500, expected: true },
    { operator: '=', value: 501, expected: false },
  ])(
    'evaluates amount $operator $value against payload.amount=500 -> $expected',
    ({ operator, value, expected }) => {
      expect(
        matchesFilters(baseEvent, { amount: { operator, value }, text: [] }),
      ).toBe(expected);
    },
  );

  it('parses numeric string amounts in payload', () => {
    const eventWithStringAmount = {
      ...baseEvent,
      payload: { amount: '1250.75' },
    };
    expect(
      matchesFilters(eventWithStringAmount, {
        amount: { operator: '>', value: 1200 },
        text: [],
      }),
    ).toBe(true);
    expect(
      matchesFilters(eventWithStringAmount, {
        amount: { operator: '<', value: 1200 },
        text: [],
      }),
    ).toBe(false);
  });

  it('rejects when payload.amount exists but is non-numeric', () => {
    const eventWithBadAmount = {
      ...baseEvent,
      payload: { amount: 'not-a-number' },
    };
    expect(
      matchesFilters(eventWithBadAmount, {
        amount: { operator: '>', value: 0 },
        text: [],
      }),
    ).toBe(false);
  });

  it('does not filter out events whose payload is missing or lacks amount (current implementation)', () => {
    const amountFilter: SearchFilters = {
      amount: { operator: '>', value: 100 },
      text: [],
    };
    expect(matchesFilters({ eventType: 'swap', contractId: 'C1' }, amountFilter)).toBe(true);
    expect(
      matchesFilters({ eventType: 'swap', contractId: 'C1', payload: null }, amountFilter),
    ).toBe(true);
    expect(
      matchesFilters({ eventType: 'swap', contractId: 'C1', payload: { other: 1 } }, amountFilter),
    ).toBe(true);
  });

  it('matches free-text terms case-insensitively across eventType, contractId, and payload', () => {
    expect(
      matchesFilters(baseEvent, { text: ['tokentransfer', 'gbbbb', 'deposit'] }),
    ).toBe(true);
    expect(matchesFilters(baseEvent, { text: ['tokentransfer', 'missing'] })).toBe(
      false,
    );
  });

  it('handles events without payload when matching free text', () => {
    const noPayloadEvent = { eventType: 'Mint', contractId: 'CMINT123' };
    expect(matchesFilters(noPayloadEvent, { text: ['mint', 'cmint'] })).toBe(true);
    expect(matchesFilters(noPayloadEvent, { text: ['deposit'] })).toBe(false);
  });
});
