"""17L: UI-side collaboration review with explicit per-live-stage approvals.

The desktop controls (not model output) must call this on its Tk thread.
Never execute tools, read memory, or contact providers in this module.
"""
from varyn.collaboration import Stage
from varyn.desktop_controller import DEFAULT_MODELS, PROVIDERS

ROLES = ("analyst", "critic", "synthesizer")


def review_collaboration(task, selections, *, network_enabled=False,
                         ask_approval=None, memory_attached=False):
    """Return frozen stages/confirmations only after reviewing EACH live step.

    All model IDs and role order are validated before showing any approval
    dialog or returning a potentially dispatchable plan. The prompt explicitly
    discloses that original task AND earlier AI outputs reach later providers.
    Approval callback is controlled by the GUI, never by an LLM or a file.
    """
    if type(memory_attached) is not bool:
        raise ValueError("Memory attachment flag must be boolean")
    if type(task) is not str or not 1 <= len(task.strip()) <= 1200:
        raise ValueError("Task must be 1..1200 characters")
    if (type(selections) not in (tuple, list) or len(selections) != 3 or
            any(type(row) not in (tuple, list) or len(row) != 2
                for row in selections)):
        raise ValueError("Exactly three provider/model selections are required")
    stages = []
    for role, (provider, model) in zip(ROLES, selections):
        if type(provider) is not str or provider not in PROVIDERS:
            raise ValueError("Unknown stage provider")
        if type(model) is not str:
            raise ValueError("Invalid model identifier")
        stages.append(Stage(role, provider, model, 256))
    stages = tuple(stages)
    confirmations = []
    for index, stage in enumerate(stages):
        if stage.provider == "fake":
            confirmations.append(False)
            continue
        if network_enabled is not True or not callable(ask_approval):
            raise PermissionError("External collaboration needs network consent and UI review")
        warning = (
            f"Step {index + 1}/3: {stage.role}\n"
            f"Provider: {stage.provider}\nModel: {stage.model}\n\n"
            "This developer API call can incur charges. The original task "
            "will be sent to this provider. For critic/synthesizer, earlier "
            "model outputs will ALSO be sent across provider boundaries as "
            "UNTRUSTED input (up to 950 characters per previous stage). "
            + ("The EXACT user-selected local memory records will be sent "
             "to the analyst stage; later stages may receive quoted or "
             "summarized contents via model outputs.\n\n"
             if memory_attached else "No stored memory is attached.\n\n")
            + "Approve this EXACT API stage, its possible cost, and data sharing?"
        )
        if ask_approval(warning) is not True:
            raise PermissionError("Collaboration plan declined; nothing was dispatched")
        confirmations.append(True)
    return stages, tuple(confirmations)
