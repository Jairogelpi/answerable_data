class PlanningError(RuntimeError):
    pass


class DuplicateSkill(PlanningError):
    pass


class UnknownCheckType(PlanningError):
    pass


class DuplicateCheck(PlanningError):
    pass


class MissingDependency(PlanningError):
    pass


class CyclicCheckPlan(PlanningError):
    pass
