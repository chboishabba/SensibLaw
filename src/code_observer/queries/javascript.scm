(function_declaration
  name: (identifier) @symbol.name) @symbol.declaration

(class_declaration
  name: (identifier) @symbol.name) @symbol.declaration

(method_definition
  name: (_) @symbol.name) @symbol.declaration

(lexical_declaration
  (variable_declarator
    name: (identifier) @symbol.name
    value: [
      (arrow_function)
      (function_expression)
      (class)
    ])) @symbol.declaration

(import_statement) @import.observed

(call_expression
  function: (_) @call.callee) @call.observed

(call_expression
  function: (_) @test.assertion.callee) @test.assertion

(object
  (pair
    key: (_) @schema.field)) @schema.literal
