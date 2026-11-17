import { readFileSync } from "node:fs";
import ts from "typescript";

// Execute the actual handler body with isolated boundary dependencies, without
// starting Vite or connecting tests to production Supabase/provider accounts.
export function sourceFunction(path, name, dependencies = {}) {
  const source = ts.createSourceFile(
    path,
    readFileSync(new URL(path, import.meta.url), "utf8"),
    ts.ScriptTarget.Latest,
    true,
    path.endsWith("tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  let declaration;
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name?.text === name) declaration = node;
    else ts.forEachChild(node, visit);
  }
  visit(source);
  if (!declaration) throw new Error(`Missing function ${name}`);
  const code = ts.transpileModule(declaration.getText(source).replace(/^export\s+/, ""), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
  }).outputText;
  return new Function(...Object.keys(dependencies), `${code}; return ${name};`)(
    ...Object.values(dependencies),
  );
}

export function sourceCallback(path, method, dependencies = {}) {
  const source = ts.createSourceFile(
    path,
    readFileSync(new URL(path, import.meta.url), "utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  let callback;
  function visit(node) {
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.name.text === method
    )
      callback = node.arguments[0];
    else ts.forEachChild(node, visit);
  }
  visit(source);
  if (!callback) throw new Error(`Missing callback ${method}`);
  const code = ts.transpileModule(`const callback = ${callback.getText(source)};`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
  }).outputText;
  return new Function(...Object.keys(dependencies), `${code}; return callback;`)(
    ...Object.values(dependencies),
  );
}
