import assert from "node:assert/strict";
import test, { before, after } from "node:test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const container = process.env.FURINA_PG_TEST_CONTAINER;
const db = `furina_nvidia_test_${process.pid}`;
const sql = (text, role) =>
  execFileSync(
    "docker",
    ["exec", "-i", container, "psql", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-At"],
    {
      input: (role ? `set role ${role};\n` : "") + text,
      encoding: "utf8",
      stdio: ["pipe", "pipe", "pipe"],
    },
  );
const owner = "00000000-0000-4000-8000-000000000001";
const other = "00000000-0000-4000-8000-000000000002";
const keyId = "00000000-0000-4000-8000-000000000003";
before(() => {
  if (!container) return;
  execFileSync("docker", ["exec", container, "createdb", "-U", "postgres", db]);
  sql(`do $$ begin create role anon; exception when duplicate_object then null; end $$;
    do $$ begin create role authenticated; exception when duplicate_object then null; end $$;
    do $$ begin create role service_role bypassrls; exception when duplicate_object then null; end $$;
    create schema auth; create table auth.users (id uuid primary key);
    insert into auth.users values ('${owner}'),('${other}');`);
  sql(
    readFileSync(
      new URL("../supabase/migrations/20261115170000_furina_ai_usage.sql", import.meta.url),
      "utf8",
    ),
  );
  sql(
    readFileSync(
      new URL("../supabase/migrations/20261118021140_furina_nvidia_main_chat.sql", import.meta.url),
      "utf8",
    ),
  );
  sql(`insert into public.furina_nvidia_chat_keys(id,user_id,encrypted_value,fingerprint,suffix)
    values ('${keyId}','${owner}','synthetic-encrypted-value','synthetic-fingerprint','test');`);
});
after(() => {
  if (container) execFileSync("docker", ["exec", container, "dropdb", "-U", "postgres", db]);
});

test(
  "migration preserves old provider defaults and records NVIDIA usage",
  { skip: !container },
  () => {
    assert.equal(
      sql(
        `insert into public.furina_ai_preferences(user_id) values('${owner}') returning chat_provider || ':' || use_nvidia_chat;`,
      ).split("\n")[0],
      "gemini:false",
    );
    sql(`select public.record_furina_chat_usage('${owner}','nvidia',25);`);
    assert.equal(
      sql(
        `select provider || ':' || tokens from public.furina_chat_usage where user_id='${owner}';`,
      ).trim(),
      "nvidia:25",
    );
  },
);
test(
  "anonymous and authenticated clients cannot access encrypted keys, state or its RPC",
  { skip: !container },
  () => {
    for (const role of ["anon", "authenticated"]) {
      for (const table of ["furina_nvidia_chat_keys", "furina_nvidia_chat_state"])
        assert.throws(() => sql(`select * from public.${table};`, role), /permission denied/);
      assert.throws(
        () =>
          sql(`select public.save_furina_nvidia_chat_state('${owner}',null,null,'{}',null);`, role),
        /permission denied/,
      );
    }
  },
);
test(
  "routing state merges cooldowns conservatively and retains a successful model across later errors",
  { skip: !container },
  () => {
    const future = Date.now() + 120000;
    sql(
      `select public.save_furina_nvidia_chat_state('${owner}','minimaxai/minimax-m3.1-flash','${keyId}','{"key:a":${future}}',null);`,
      "service_role",
    );
    sql(
      `select public.save_furina_nvidia_chat_state('${owner}',null,null,'{"key:a":${future - 1000},"model:b":${future}}','busy');`,
      "service_role",
    );
    const state = JSON.parse(
      sql(
        `select row_to_json(s) from public.furina_nvidia_chat_state s where user_id='${owner}';`,
      ).trim(),
    );
    assert.equal(state.active_model, "minimaxai/minimax-m3.1-flash");
    assert.equal(state.active_key_id, keyId);
    assert.equal(state.cooldowns["key:a"], future);
    assert.equal(state.cooldowns["model:b"], future);
  },
);
test(
  "routing never links another account's key and key removal clears its reference",
  { skip: !container },
  () => {
    sql(
      `select public.save_furina_nvidia_chat_state('${other}','model','${keyId}','{}',null);`,
      "service_role",
    );
    assert.equal(
      sql(
        `select active_key_id is null from public.furina_nvidia_chat_state where user_id='${other}';`,
      ).trim(),
      "t",
    );
    sql(`delete from public.furina_nvidia_chat_keys where id='${keyId}';`);
    assert.equal(
      sql(
        `select active_key_id is null from public.furina_nvidia_chat_state where user_id='${owner}';`,
      ).trim(),
      "t",
    );
  },
);
