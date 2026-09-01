import RequestProject.DisjointUnion

/-!
# `union of` (P2737) and class intersections

`RequestProject.DisjointUnion` covers `disjoint union of` (P2738), the strongest of the
class-decomposition statements.  Wikidata also has the weaker `union of` (P2737), which
carves a class into subclasses that are allowed to **overlap**, and — although Wikidata
has no dedicated property for it — classes that are *intersections* of others (a class
that is a subclass of several classes and contains every item that is an instance of all
of them) occur constantly in the ontology.

This file adds both:

* `Wikidata.Ontology.IsUnion O c Part`: every part is a subclass of `c` and every
  instance of `c` is an instance of some part.  Proved: the instances of the union are
  exactly the instances of the parts; a disjoint union is a union; the union is empty
  when all parts are; unions compose under refinement; a union with a single part has
  the same instances as that part; and everything the parts have in common (being a
  subclass of a further class, in the sense of inherited instances) is inherited by
  the union.
* `Wikidata.Ontology.IsIntersection O c Part`: `c` is a subclass of every part and every
  item instantiating all the parts is an instance of `c`.  Proved: the instances of the
  intersection are exactly the items lying in all the parts; the intersection of two
  disjoint classes is empty; the intersection is the largest such class; and an
  intersection over the parts of a union of which one part exhausts the class collapses
  to that part.
* Certified executable checkers `Wikidata.KB.unionOk` and `Wikidata.KB.interOk`.
* A worked fragment where `artist` is the union of `painter` and `sculptor` — which is
  *not* a disjoint union, since Michelangelo is both — and where the class of
  painter-sculptors is checked to be their intersection.

Note on the degenerate case: an intersection over the empty family of parts is the class
of *all* items, which is what the definition says; the executable checker therefore
requires a nonempty list of parts.
-/

namespace Wikidata

namespace Ontology

variable {I : Type*} {O : Ontology I}

/-! ### `union of` (P2737) -/

/-- `IsUnion O c Part`: the class `c` is the union (P2737) of the classes satisfying
`Part` — each part is a subclass of `c`, and every instance of `c` is an instance of at
least one part.  Unlike `IsDisjointUnion` the parts may overlap. -/
structure IsUnion (O : Ontology I) (c : I) (Part : I → Prop) : Prop where
  /-- Every part is a subclass of the whole. -/
  subclass : ∀ ⦃p⦄, Part p → O.SubclassOf p c
  /-- Every instance of the whole is an instance of some part. -/
  cover : ∀ ⦃a⦄, O.InstanceOf a c → ∃ p, Part p ∧ O.InstanceOf a p

namespace IsUnion

variable {c : I} {Part : I → Prop} (h : IsUnion O c Part)
include h

/-- An instance of a part is an instance of the whole. -/
theorem instanceOf_of_part {a p : I} (hp : Part p) (ha : O.InstanceOf a p) :
    O.InstanceOf a c :=
  instanceOf_trans_subclassOf ha (h.subclass hp)

/-- The instances of the union are exactly the instances of its parts. -/
theorem instanceOf_iff {a : I} : O.InstanceOf a c ↔ ∃ p, Part p ∧ O.InstanceOf a p :=
  ⟨fun ha => h.cover ha, fun ⟨_, hp, ha⟩ => h.instanceOf_of_part hp ha⟩

/-- The union of classes without instances has no instances. -/
theorem not_hasInstance (hempty : ∀ p, Part p → ¬ O.HasInstance p) : ¬ O.HasInstance c := by
  rintro ⟨a, ha⟩
  obtain ⟨p, hp, hap⟩ := h.cover ha
  exact hempty p hp ⟨a, hap⟩

/-- A property shared by all the parts — every instance of a part being an instance of
`d` — is inherited by the union. -/
theorem instanceOf_of_forall_parts {d : I}
    (hd : ∀ p, Part p → ∀ a, O.InstanceOf a p → O.InstanceOf a d) {a : I}
    (ha : O.InstanceOf a c) : O.InstanceOf a d := by
  obtain ⟨p, hp, hap⟩ := h.cover ha
  exact hd p hp a hap

/-- A union with a single part has exactly the instances of that part. -/
theorem instanceOf_iff_of_singleton {p : I} (hpart : ∀ q, Part q ↔ q = p) {a : I} :
    O.InstanceOf a c ↔ O.InstanceOf a p := by
  refine ⟨fun ha => ?_, fun ha => h.instanceOf_of_part ((hpart p).2 rfl) ha⟩
  obtain ⟨q, hq, haq⟩ := h.cover ha
  rw [hpart q] at hq
  exact hq ▸ haq

/-- Unions compose: refining every part of a union again yields a union. -/
theorem comp {Sub : I → I → Prop} (hsub : ∀ p, Part p → IsUnion O p (Sub p)) :
    IsUnion O c (fun q => ∃ p, Part p ∧ Sub p q) where
  subclass := by
    rintro q ⟨p, hp, hq⟩
    exact subclassOf_trans ((hsub p hp).subclass hq) (h.subclass hp)
  cover := by
    intro a ha
    obtain ⟨p, hp, hap⟩ := h.cover ha
    obtain ⟨q, hq, haq⟩ := (hsub p hp).cover hap
    exact ⟨q, ⟨p, hp, hq⟩, haq⟩

end IsUnion

/-- A disjoint union (P2738) is in particular a union (P2737). -/
theorem IsDisjointUnion.isUnion {c : I} {Part : I → Prop}
    (h : IsDisjointUnion O c Part) : IsUnion O c Part where
  subclass := h.subclass
  cover := h.cover

/-! ### Intersections -/

/-- `IsIntersection O c Part`: the class `c` is the intersection of the classes
satisfying `Part` — it is a subclass of each of them, and every item that instantiates
all of them is an instance of `c`. -/
structure IsIntersection (O : Ontology I) (c : I) (Part : I → Prop) : Prop where
  /-- The intersection is a subclass of each part. -/
  subclass : ∀ ⦃p⦄, Part p → O.SubclassOf c p
  /-- An item instantiating every part is an instance of the intersection. -/
  complete : ∀ ⦃a⦄, (∀ p, Part p → O.InstanceOf a p) → O.InstanceOf a c

namespace IsIntersection

variable {c : I} {Part : I → Prop} (h : IsIntersection O c Part)
include h

/-- An instance of the intersection is an instance of each part. -/
theorem instanceOf_part {a p : I} (hp : Part p) (ha : O.InstanceOf a c) : O.InstanceOf a p :=
  instanceOf_trans_subclassOf ha (h.subclass hp)

/-- The instances of the intersection are exactly the items lying in every part. -/
theorem instanceOf_iff {a : I} : O.InstanceOf a c ↔ ∀ p, Part p → O.InstanceOf a p :=
  ⟨fun ha _ hp => h.instanceOf_part hp ha, fun ha => h.complete ha⟩

/-- The intersection is the largest such class: if every instance of a class `d` lies
in all the parts, then every instance of `d` is an instance of the intersection. -/
theorem instanceOf_of_subclass_all {d a : I}
    (hd : ∀ p, Part p → ∀ x, O.InstanceOf x d → O.InstanceOf x p) (hda : O.InstanceOf a d) :
    O.InstanceOf a c :=
  h.complete fun p hp => hd p hp a hda

omit h in
/-- The intersection of two classes declared disjoint has no instances. -/
theorem not_hasInstance_of_disjoint {D : WithDisjointness I}
    (h : IsIntersection D.toOntology c Part) {p q : I} (hp : Part p) (hq : Part q)
    (hdisj : D.DisjointWith p q) : ¬ D.toOntology.HasInstance c := by
  rintro ⟨a, ha⟩
  exact D.disjointWith_spec hdisj (h.instanceOf_part hp ha) (h.instanceOf_part hq ha)

/-- If one of the parts is already contained in all the others, the intersection has
exactly its instances. -/
theorem instanceOf_iff_of_smallest {p : I} (hp : Part p)
    (hmin : ∀ q, Part q → ∀ a, O.InstanceOf a p → O.InstanceOf a q) {a : I} :
    O.InstanceOf a c ↔ O.InstanceOf a p :=
  ⟨fun ha => h.instanceOf_part hp ha, fun ha => h.complete fun q hq => hmin q hq a ha⟩

end IsIntersection

end Ontology

/-! ### The executable checkers -/

namespace KB

variable (kb : KB)

/-- The `union of` (P2737) check: every listed class is a subclass of `c`, and every
instance of `c` is an instance of one of them. -/
def unionOk (c : Qid) (ps : List Qid) : Bool :=
  kb.dunSubclassOk c ps && kb.dunCoverOk c ps

/-- The intersection check: `c` is a subclass of every listed class, and every item
instantiating all of them is an instance of `c`.  The list must be nonempty. -/
def interOk (c : Qid) (ps : List Qid) : Bool :=
  !ps.isEmpty && ps.all (fun p => kb.isSubclassOf c p) &&
    kb.items.all (fun a => !ps.all (fun p => kb.isInstanceOf a p) || kb.isInstanceOf a c)

variable {kb}

/-- **Soundness of the union checker.** -/
theorem isUnion_of_unionOk (hv : kb.valid = true) {c : Qid} {ps : List Qid}
    (h : kb.unionOk c ps = true) :
    Ontology.IsUnion (kb.toOntology hv) c (fun p => p ∈ ps) := by
  simp only [unionOk, Bool.and_eq_true] at h
  obtain ⟨hsub, hcov⟩ := h
  refine ⟨?_, ?_⟩
  · intro p hp
    exact (isSubclassOf_iff_subclassOf hv p c).1 (List.all_eq_true.1 hsub p hp)
  · intro a ha
    have hmem : a ∈ kb.instancesOf c :=
      mem_instancesOf.2 ⟨mem_items_of_instanceOf hv ha,
        (isInstanceOf_iff_instanceOf hv a c).2 ha⟩
    obtain ⟨p, hp, hap⟩ := List.any_eq_true.1 (List.all_eq_true.1 hcov a hmem)
    exact ⟨p, hp, (isInstanceOf_iff_instanceOf hv a p).1 hap⟩

/-- **Soundness of the intersection checker.** -/
theorem isIntersection_of_interOk (hv : kb.valid = true) {c : Qid} {ps : List Qid}
    (h : kb.interOk c ps = true) :
    Ontology.IsIntersection (kb.toOntology hv) c (fun p => p ∈ ps) := by
  simp only [interOk, Bool.and_eq_true] at h
  obtain ⟨⟨hne, hsub⟩, hcomp⟩ := h
  refine ⟨?_, ?_⟩
  · intro p hp
    exact (isSubclassOf_iff_subclassOf hv c p).1 (List.all_eq_true.1 hsub p hp)
  · intro a ha
    obtain ⟨p, hp⟩ := List.exists_mem_of_ne_nil ps (by
      simpa [List.isEmpty_iff] using hne)
    have hamem : a ∈ kb.items := mem_items_of_instanceOf hv (ha p hp)
    have hall : ps.all (fun q => kb.isInstanceOf a q) = true :=
      List.all_eq_true.2 fun q hq => (isInstanceOf_iff_instanceOf hv a q).2 (ha q hq)
    have := List.all_eq_true.1 hcomp a hamem
    rw [hall] at this
    simp only [Bool.not_true, Bool.false_or] at this
    exact (isInstanceOf_iff_instanceOf hv a c).1 this

end KB

/-! ### A worked fragment -/

namespace ClassAlgebraExample

open KB

/-- Abbreviation for a Wikidata item. -/
def Q (s : String) : Qid := .wd s

/-- English labels for the identifiers used below. -/
def labels : List (Qid × String) :=
  [(Q "Q483501", "artist"), (Q "Q1028181", "painter"), (Q "Q1281618", "sculptor"),
   (Q "Q5592", "Michelangelo"), (Q "Q762", "Leonardo da Vinci"),
   (Q "Q-painter-sculptor", "painter-sculptor")]

/-- The label of an identifier, or its raw form if none is recorded. -/
def labelOf (q : Qid) : String := (labels.lookup q).getD (toString (repr q))

/-- `painter` and `sculptor` are subclasses of `artist`; Michelangelo is both, Leonardo
is (here) only a painter; `painter-sculptor` is the class of those who are both. -/
def artistKB : KB where
  name := "wd-class-algebra"
  items := [Q "Q483501", Q "Q1028181", Q "Q1281618", Q "Q-painter-sculptor",
            Q "Q5592", Q "Q762"]
  levels := [(Q "Q483501", 1), (Q "Q1028181", 1), (Q "Q1281618", 1),
             (Q "Q-painter-sculptor", 1), (Q "Q5592", 0), (Q "Q762", 0)]
  sub := [(Q "Q1028181", Q "Q483501"), (Q "Q1281618", Q "Q483501"),
          (Q "Q-painter-sculptor", Q "Q1028181"), (Q "Q-painter-sculptor", Q "Q1281618")]
  inst := [(Q "Q5592", Q "Q-painter-sculptor"), (Q "Q762", Q "Q1028181")]

set_option maxRecDepth 40000 in
theorem artistKB_valid : artistKB.valid = true := by decide

set_option maxRecDepth 40000 in
/-- `artist` is the union (P2737) of `painter` and `sculptor`. -/
theorem artistKB_unionOk :
    artistKB.unionOk (Q "Q483501") [Q "Q1028181", Q "Q1281618"] = true := by decide

set_option maxRecDepth 40000 in
/-- It is *not* a disjoint union: Michelangelo is both a painter and a sculptor. -/
theorem artistKB_not_dunOk :
    artistKB.dunOk (Q "Q483501") [Q "Q1028181", Q "Q1281618"] = false := by decide

/-- Hence, abstractly, `artist` is the union of the two classes. -/
theorem artistKB_isUnion :
    Ontology.IsUnion (artistKB.toOntology artistKB_valid) (Q "Q483501")
      (fun p => p ∈ [Q "Q1028181", Q "Q1281618"]) :=
  KB.isUnion_of_unionOk artistKB_valid artistKB_unionOk

/-- Every artist of the fragment is a painter or a sculptor. -/
theorem artist_painter_or_sculptor {a : Qid}
    (ha : (artistKB.toOntology artistKB_valid).InstanceOf a (Q "Q483501")) :
    (artistKB.toOntology artistKB_valid).InstanceOf a (Q "Q1028181") ∨
      (artistKB.toOntology artistKB_valid).InstanceOf a (Q "Q1281618") := by
  obtain ⟨p, hp, hap⟩ := artistKB_isUnion.cover ha
  rcases List.mem_cons.1 hp with rfl | hp
  · exact Or.inl hap
  · have : p = Q "Q1281618" := by simpa using hp
    exact Or.inr (this ▸ hap)

set_option maxRecDepth 40000 in
/-- `painter-sculptor` is the intersection of `painter` and `sculptor`. -/
theorem artistKB_interOk :
    artistKB.interOk (Q "Q-painter-sculptor") [Q "Q1028181", Q "Q1281618"] = true := by decide

/-- Hence, abstractly, it really is their intersection. -/
theorem artistKB_isIntersection :
    Ontology.IsIntersection (artistKB.toOntology artistKB_valid) (Q "Q-painter-sculptor")
      (fun p => p ∈ [Q "Q1028181", Q "Q1281618"]) :=
  KB.isIntersection_of_interOk artistKB_valid artistKB_interOk

/-- Michelangelo, being both, is an instance of the intersection. -/
theorem michelangelo_mem_intersection :
    (artistKB.toOntology artistKB_valid).InstanceOf (Q "Q5592") (Q "Q-painter-sculptor") :=
  (KB.isInstanceOf_iff_instanceOf artistKB_valid _ _).1 (by decide)

set_option maxRecDepth 40000 in
/-- Leonardo is not a sculptor in this fragment, so the intersection check rejects the
claim that `painter` alone is the intersection of `painter` and `sculptor`. -/
theorem artistKB_interOk_wrong :
    artistKB.interOk (Q "Q1028181") [Q "Q1028181", Q "Q1281618"] = false := by decide

end ClassAlgebraExample

end Wikidata
