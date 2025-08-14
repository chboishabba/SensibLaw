package consent

# List of cultural flags requiring explicit consent
sensitive_flags = {"sacred", "restricted", "no_store", "no_share"}

default allow = true

allow = false {
    some flag
    input.cultural_flags[_] == flag
    flag == sensitive_flags[_]
    not input.consent
}

allow = false {
    input.consent_required
    not input.consent
}
