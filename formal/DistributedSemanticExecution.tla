---- MODULE DistributedSemanticExecution ----
EXTENDS Integers, FiniteSets, Naturals, Sequences, TLC

CONSTANTS Jobs, Owners, Workers, JobOwner, Dependencies, MaxAttempts

ASSUME Jobs # {} /\ Owners # {} /\ Workers # {}
ASSUME JobOwner \in [Jobs -> Owners]
ASSUME Dependencies \in [Jobs -> SUBSET Jobs]
ASSUME MaxAttempts \in Nat \ {0}

JobStates == {"blocked", "ready", "leased", "completed", "retryable", "failed"}
DeltaStates == {"none", "computed", "accepted", "stale"}

VARIABLES
    jobState,
    leaseEpoch,
    leaseOwner,
    attemptCount,
    ownerRevision,
    expectedRevision,
    deltaState,
    deltaEpoch,
    admittedRevision,
    coverageClosed,
    ownerDirty,
    obligations

vars == <<
    jobState,
    leaseEpoch,
    leaseOwner,
    attemptCount,
    ownerRevision,
    expectedRevision,
    deltaState,
    deltaEpoch,
    admittedRevision,
    coverageClosed,
    ownerDirty,
    obligations
>>

DependenciesComplete(j) ==
    \A dependency \in Dependencies[j] : jobState[dependency] = "completed"

Init ==
    /\ jobState = [j \in Jobs |-> IF Dependencies[j] = {} THEN "ready" ELSE "blocked"]
    /\ leaseEpoch = [j \in Jobs |-> 0]
    /\ leaseOwner = [j \in Jobs |-> CHOOSE x : x \notin Workers]
    /\ attemptCount = [j \in Jobs |-> 0]
    /\ ownerRevision = [o \in Owners |-> 0]
    /\ expectedRevision = [j \in Jobs |-> 0]
    /\ deltaState = [j \in Jobs |-> "none"]
    /\ deltaEpoch = [j \in Jobs |-> 0]
    /\ admittedRevision = [j \in Jobs |-> 0]
    /\ coverageClosed = [o \in Owners |-> FALSE]
    /\ ownerDirty = [o \in Owners |-> FALSE]
    /\ obligations = [o \in Owners |-> 0]

Awaken(j) ==
    /\ jobState[j] = "blocked"
    /\ DependenciesComplete(j)
    /\ jobState' = [jobState EXCEPT ![j] = "ready"]
    /\ UNCHANGED <<
        leaseEpoch, leaseOwner, attemptCount, ownerRevision,
        expectedRevision, deltaState, deltaEpoch, admittedRevision,
        coverageClosed, ownerDirty, obligations
    >>

Lease(j, w) ==
    /\ jobState[j] \in {"ready", "retryable"}
    /\ attemptCount[j] < MaxAttempts
    /\ jobState' = [jobState EXCEPT ![j] = "leased"]
    /\ leaseEpoch' = [leaseEpoch EXCEPT ![j] = @ + 1]
    /\ leaseOwner' = [leaseOwner EXCEPT ![j] = w]
    /\ attemptCount' = [attemptCount EXCEPT ![j] = @ + 1]
    /\ expectedRevision' = [expectedRevision EXCEPT
        ![j] = ownerRevision[JobOwner[j]]]
    /\ deltaState' = [deltaState EXCEPT ![j] = "none"]
    /\ deltaEpoch' = [deltaEpoch EXCEPT ![j] = 0]
    /\ admittedRevision' = [admittedRevision EXCEPT ![j] = 0]
    /\ UNCHANGED <<ownerRevision, coverageClosed, ownerDirty, obligations>>

Compute(j, w, e) ==
    /\ jobState[j] = "leased"
    /\ leaseOwner[j] = w
    /\ leaseEpoch[j] = e
    /\ deltaState[j] = "none"
    /\ deltaState' = [deltaState EXCEPT ![j] = "computed"]
    /\ deltaEpoch' = [deltaEpoch EXCEPT ![j] = e]
    /\ UNCHANGED <<
        jobState, leaseEpoch, leaseOwner, attemptCount, ownerRevision,
        expectedRevision, admittedRevision, coverageClosed,
        ownerDirty, obligations
    >>

Admit(j, w, e) ==
    LET owner == JobOwner[j] IN
    /\ jobState[j] = "leased"
    /\ leaseOwner[j] = w
    /\ leaseEpoch[j] = e
    /\ deltaState[j] = "computed"
    /\ deltaEpoch[j] = e
    /\ expectedRevision[j] = ownerRevision[owner]
    /\ deltaState' = [deltaState EXCEPT ![j] = "accepted"]
    /\ ownerRevision' = [ownerRevision EXCEPT ![owner] = @ + 1]
    /\ admittedRevision' = [admittedRevision EXCEPT
        ![j] = ownerRevision[owner] + 1]
    /\ jobState' = [jobState EXCEPT ![j] = "completed"]
    /\ ownerDirty' = [ownerDirty EXCEPT ![owner] = TRUE]
    /\ UNCHANGED <<
        leaseEpoch, leaseOwner, attemptCount, expectedRevision,
        deltaEpoch, coverageClosed, obligations
    >>

RejectStale(j, w, e) ==
    LET owner == JobOwner[j] IN
    /\ jobState[j] = "leased"
    /\ leaseOwner[j] = w
    /\ leaseEpoch[j] = e
    /\ deltaState[j] = "computed"
    /\ \/ deltaEpoch[j] # leaseEpoch[j]
       \/ expectedRevision[j] # ownerRevision[owner]
    /\ deltaState' = [deltaState EXCEPT ![j] = "stale"]
    /\ jobState' = [jobState EXCEPT
        ![j] = IF attemptCount[j] < MaxAttempts THEN "retryable" ELSE "failed"]
    /\ UNCHANGED <<
        leaseEpoch, leaseOwner, attemptCount, ownerRevision,
        expectedRevision, deltaEpoch, admittedRevision,
        coverageClosed, ownerDirty, obligations
    >>

Expire(j) ==
    /\ jobState[j] = "leased"
    /\ deltaState[j] \in {"none", "computed"}
    /\ jobState' = [jobState EXCEPT
        ![j] = IF attemptCount[j] < MaxAttempts THEN "retryable" ELSE "failed"]
    /\ deltaState' = [deltaState EXCEPT
        ![j] = IF @ = "computed" THEN "stale" ELSE @]
    /\ UNCHANGED <<
        leaseEpoch, leaseOwner, attemptCount, ownerRevision,
        expectedRevision, deltaEpoch, admittedRevision,
        coverageClosed, ownerDirty, obligations
    >>

ReduceOwner(o) ==
    /\ ownerDirty[o]
    /\ ownerDirty' = [ownerDirty EXCEPT ![o] = FALSE]
    /\ UNCHANGED <<
        jobState, leaseEpoch, leaseOwner, attemptCount, ownerRevision,
        expectedRevision, deltaState, deltaEpoch, admittedRevision,
        coverageClosed, obligations
    >>

CloseCoverage(o) ==
    /\ ~coverageClosed[o]
    /\ coverageClosed' = [coverageClosed EXCEPT ![o] = TRUE]
    /\ UNCHANGED <<
        jobState, leaseEpoch, leaseOwner, attemptCount, ownerRevision,
        expectedRevision, deltaState, deltaEpoch, admittedRevision,
        ownerDirty, obligations
    >>

DischargeObligation(o) ==
    /\ obligations[o] > 0
    /\ obligations' = [obligations EXCEPT ![o] = @ - 1]
    /\ UNCHANGED <<
        jobState, leaseEpoch, leaseOwner, attemptCount, ownerRevision,
        expectedRevision, deltaState, deltaEpoch, admittedRevision,
        coverageClosed, ownerDirty
    >>

Next ==
    \/ \E j \in Jobs : Awaken(j)
    \/ \E j \in Jobs, w \in Workers : Lease(j, w)
    \/ \E j \in Jobs, w \in Workers, e \in Nat : Compute(j, w, e)
    \/ \E j \in Jobs, w \in Workers, e \in Nat : Admit(j, w, e)
    \/ \E j \in Jobs, w \in Workers, e \in Nat : RejectStale(j, w, e)
    \/ \E j \in Jobs : Expire(j)
    \/ \E o \in Owners : ReduceOwner(o)
    \/ \E o \in Owners : CloseCoverage(o)
    \/ \E o \in Owners : DischargeObligation(o)

TypeOK ==
    /\ jobState \in [Jobs -> JobStates]
    /\ leaseEpoch \in [Jobs -> Nat]
    /\ attemptCount \in [Jobs -> 0..MaxAttempts]
    /\ ownerRevision \in [Owners -> Nat]
    /\ expectedRevision \in [Jobs -> Nat]
    /\ deltaState \in [Jobs -> DeltaStates]
    /\ deltaEpoch \in [Jobs -> Nat]
    /\ admittedRevision \in [Jobs -> Nat]
    /\ coverageClosed \in [Owners -> BOOLEAN]
    /\ ownerDirty \in [Owners -> BOOLEAN]
    /\ obligations \in [Owners -> Nat]

LeaseFencingSafety ==
    \A j \in Jobs :
        deltaState[j] = "accepted" => deltaEpoch[j] = leaseEpoch[j]

ExactlyOneSemanticAdmission ==
    \A j \in Jobs :
        deltaState[j] = "accepted" =>
            /\ jobState[j] = "completed"
            /\ admittedRevision[j] > 0

OwnerRevisionAgreement ==
    \A j \in Jobs :
        deltaState[j] = "accepted" =>
            admittedRevision[j] <= ownerRevision[JobOwner[j]]

CompletedDependencies ==
    \A j \in Jobs :
        jobState[j] \in {"ready", "leased", "completed"} =>
            DependenciesComplete(j)

DocumentFixed ==
    /\ \A j \in Jobs : jobState[j] \in {"completed", "failed"}
    /\ \A o \in Owners : ~ownerDirty[o]
    /\ \A o \in Owners : coverageClosed[o]
    /\ \A o \in Owners : obligations[o] = 0

FixedPointSoundness ==
    DocumentFixed =>
        /\ ~\E j \in Jobs : jobState[j] \in {"ready", "leased", "retryable"}
        /\ ~\E o \in Owners : ownerDirty[o]

Safety ==
    TypeOK
    /\ LeaseFencingSafety
    /\ ExactlyOneSemanticAdmission
    /\ OwnerRevisionAgreement
    /\ CompletedDependencies
    /\ FixedPointSoundness

Termination ==
    \A j \in Jobs : <>(jobState[j] \in {"completed", "failed"})

Spec == Init /\ [][Next]_vars

FairSpec ==
    Spec
    /\ \A j \in Jobs : WF_vars(Awaken(j))
    /\ \A j \in Jobs, w \in Workers : WF_vars(Lease(j, w))
    /\ \A o \in Owners : WF_vars(ReduceOwner(o))

=============================================================================
