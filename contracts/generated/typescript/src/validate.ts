// DO NOT EDIT. This file is GENERATED from contracts/schema/.
//
// generator:      contracts/tools/generate.py
// regenerate:     python3 contracts/tools/generate.py
// drift check:    python3 contracts/tools/check_drift.py
// schema version: 1.0.0
// source digest:  sha256:8b522291e4e4ff31b4684e1beca67be76c01139ac7493a1d64830b5016bf8acc
//
// The JSON Schema source is normative (ADR-0101). Edits made here are
// erased on the next generation and will fail the CI drift check.

import { SPEC } from "./spec.js";

type Json = unknown;

interface RuleT {
  t: string;
  nullable?: boolean;
  ref?: string;
  const?: Json;
  enum?: Json[];
  items?: RuleT;
  minItems?: number;
  maxItems?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  minimum?: number;
  maximum?: number;
}

interface TypeEntry {
  kind: string;
  values?: string[];
  rule?: RuleT;
  discriminator?: string;
  variants?: Array<{ name: string; const: string }>;
  properties?: Record<string, RuleT>;
  required?: string[];
  additionalProperties?: boolean;
  crossFieldEqual?: string[][];
}

const TYPES = SPEC.types as Record<string, TypeEntry>;

export class ValidationFailure extends Error {
  readonly typeName: string;
  readonly errors: string[];
  constructor(typeName: string, errors: string[]) {
    super(errors.length ? `${typeName}: ${errors.join("; ")}` : typeName);
    this.name = "ValidationFailure";
    this.typeName = typeName;
    this.errors = errors;
  }
}

function err(out: string[], path: string, message: string): void {
  out.push(`${path === "" ? "$" : path}: ${message}`);
}

function matches(pattern: string, value: string): boolean {
  // Python's re.search treats a trailing `$` as "end of string or before a
  // final newline". The generator rewrites a trailing `$` to `\Z` on the
  // Python side so both languages mean "end of string". Nothing to adjust
  // here; JS `$` without the m flag already has that meaning.
  return new RegExp(pattern).test(value);
}

function isInteger(value: Json): boolean {
  return typeof value === "number" && Number.isInteger(value);
}

function checkRule(rule: RuleT, value: Json, path: string, out: string[]): void {
  if (value === null || value === undefined) {
    if (!rule.nullable) {
      err(out, path, "must not be null");
    }
    return;
  }

  switch (rule.t) {
    case "ref":
      checkType(rule.ref as string, value, path, out);
      return;

    case "const":
      if (value !== rule.const) {
        err(out, path, `must equal ${jsonRepr(rule.const as Json)}`);
      }
      return;

    case "enum":
      if (!(rule.enum as Json[]).includes(value)) {
        err(out, path, `must be one of ${(rule.enum as Json[]).map(String).join(",")}`);
      }
      return;

    case "string": {
      if (typeof value !== "string") {
        err(out, path, "must be a string");
        return;
      }
      if (rule.minLength !== undefined && value.length < rule.minLength) {
        err(out, path, `shorter than minLength ${rule.minLength}`);
      }
      if (rule.maxLength !== undefined && value.length > rule.maxLength) {
        err(out, path, `longer than maxLength ${rule.maxLength}`);
      }
      if (rule.pattern !== undefined && !matches(rule.pattern, value)) {
        err(out, path, `does not match pattern ${rule.pattern}`);
      }
      return;
    }

    case "integer": {
      if (typeof value === "boolean" || !isInteger(value)) {
        err(out, path, "must be an integer");
        return;
      }
      const n = value as number;
      if (rule.minimum !== undefined && n < rule.minimum) {
        err(out, path, `less than minimum ${rule.minimum}`);
      }
      if (rule.maximum !== undefined && n > rule.maximum) {
        err(out, path, `greater than maximum ${rule.maximum}`);
      }
      return;
    }

    case "number":
      if (typeof value !== "number") {
        err(out, path, "must be a number");
      }
      return;

    case "boolean":
      if (typeof value !== "boolean") {
        err(out, path, "must be a boolean");
      }
      return;

    case "array": {
      if (!Array.isArray(value)) {
        err(out, path, "must be an array");
        return;
      }
      if (rule.minItems !== undefined && value.length < rule.minItems) {
        err(out, path, `fewer than minItems ${rule.minItems}`);
      }
      if (rule.maxItems !== undefined && value.length > rule.maxItems) {
        err(out, path, `more than maxItems ${rule.maxItems}`);
      }
      value.forEach((item, i) => checkRule(rule.items as RuleT, item, `${path}[${i}]`, out));
      return;
    }

    case "object":
      if (typeof value !== "object" || Array.isArray(value)) {
        err(out, path, "must be an object");
      }
      return;

    default:
      return;
  }
}

function resolvePath(value: Json, dotted: string): Json {
  let node: Json = value;
  for (const part of dotted.split(".")) {
    if (typeof node !== "object" || node === null || !(part in (node as object))) {
      return null;
    }
    node = (node as Record<string, Json>)[part];
  }
  return node;
}

function checkType(typeName: string, value: Json, path: string, out: string[]): void {
  const entry = TYPES[typeName];
  if (entry === undefined) {
    err(out, path, `unknown contract type ${typeName}`);
    return;
  }

  if (entry.kind === "enum") {
    if (!(entry.values as string[]).includes(value as string)) {
      err(out, path, `must be one of ${(entry.values as string[]).join(",")}`);
    }
    return;
  }

  if (entry.kind === "alias") {
    checkRule(entry.rule as RuleT, value, path, out);
    return;
  }

  if (entry.kind === "union") {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      err(out, path, "must be an object");
      return;
    }
    const disc = entry.discriminator as string;
    const actual = (value as Record<string, Json>)[disc];
    for (const variant of entry.variants as Array<{ name: string; const: string }>) {
      if (variant.const === actual) {
        checkType(variant.name, value, path, out);
        return;
      }
    }
    const allowed = (entry.variants as Array<{ const: string }>).map((v) => v.const).join(",");
    err(
      out,
      path,
      `invalid discriminant ${disc}=${jsonRepr(actual)}; expected one of ${allowed}`,
    );
    return;
  }

  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    err(out, path, "must be an object");
    return;
  }

  const obj = value as Record<string, Json>;

  for (const name of entry.required as string[]) {
    if (!(name in obj)) {
      err(out, path === "" ? name : `${path}.${name}`, "is required");
    }
  }

  if (entry.additionalProperties === false) {
    for (const name of Object.keys(obj).sort()) {
      if (!(name in (entry.properties as Record<string, RuleT>))) {
        err(out, path === "" ? name : `${path}.${name}`, "is not permitted");
      }
    }
  }

  for (const name of Object.keys(entry.properties as Record<string, RuleT>).sort()) {
    if (name in obj) {
      const child = path === "" ? name : `${path}.${name}`;
      checkRule((entry.properties as Record<string, RuleT>)[name], obj[name], child, out);
    }
  }

  for (const pair of entry.crossFieldEqual ?? []) {
    if (resolvePath(obj, pair[0]) !== resolvePath(obj, pair[1])) {
      err(out, path, `${pair[0]} must equal ${pair[1]}`);
    }
  }
}

/**
 * Canonical JSON representation, matching the Python validator byte-for-byte.
 * Message text is part of the cross-language contract and is asserted by the
 * parity fixtures, so both sides must render values identically.
 */
function jsonRepr(value: Json): string {
  return JSON.stringify(value ?? null);
}

/** Return a sorted list of "path: message" errors. Empty means valid. */
export function validate(typeName: string, value: Json): string[] {
  const out: string[] = [];
  checkType(typeName, value, "", out);
  return out.sort();
}

export function isValid(typeName: string, value: Json): boolean {
  return validate(typeName, value).length === 0;
}

export function requireValid(typeName: string, value: Json): Json {
  const errors = validate(typeName, value);
  if (errors.length > 0) {
    throw new ValidationFailure(typeName, errors);
  }
  return value;
}

export function knownTypes(): string[] {
  return Object.keys(TYPES).sort();
}
