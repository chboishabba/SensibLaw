(function_definition
  name: (identifier) @symbol.name) @symbol.declaration

(class_definition
  name: (identifier) @symbol.name) @symbol.declaration

[
  (import_statement)
  (import_from_statement)
] @import.observed

(call
  function: (_) @call.callee) @call.observed

(assert_statement) @test.assertion

(dictionary
  (pair
    key: (_) @schema.field)) @schema.literal
