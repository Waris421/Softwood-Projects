from .. import models

def AddRFIDAttendance(cardUID: str, machineMAC: str = None):

    # Step 1: Validate the ESP
    try:
        espBox = models.RFIDBox.objects.get(mac_address=machineMAC)
    except models.RFIDBox.DoesNotExist:
        raise LookupError(f'Machine not registered: {machineMAC}')

    if not espBox.is_active:
        raise PermissionError(f'Machine is inactive: {espBox.mac_address}')

    # Step 2: Check if it's a worker card
    try:
        employeeAssignment = models.EmployeeCardAssignment.objects.select_related('Employee').get(RFIDCard__CardId=cardUID)
        models.RFIDLog.objects.create(Employee=employeeAssignment.Employee, Machine=espBox)
        return 'Scan recorded'
    except models.EmployeeCardAssignment.DoesNotExist:
        pass

    # Step 3: Check if it's a bundle card
    try:
        bundleAssignment = models.BundleCardAssignment.objects.select_related('Bundle__Cut').get(RFIDCard__CardId=cardUID)
    except models.BundleCardAssignment.DoesNotExist:
        raise LookupError(f'Card not registered: {cardUID}')

    bundle = bundleAssignment.Bundle

    # Step 4: Get allotment (physical machine + employee)
    try:
        allotment = models.BoxAllotment.objects.select_related('Machine').get(Box=espBox)
    except models.BoxAllotment.DoesNotExist:
        raise LookupError(f'No allotment found for machine: {espBox.mac_address}')

    # Step 5: Get assigned operations
    boxOperations = models.BoxOperation.objects.select_related('Operation').filter(Box=espBox)
    if not boxOperations.exists():
        raise LookupError(f'No operations assigned to machine: {espBox.mac_address}')

    # Step 6: Duplicate check
    assignedOperations = [bo.Operation for bo in boxOperations]
    if models.Serial.objects.filter(Bundle=bundle, Box=espBox, Operation__in=assignedOperations).exists():
        raise ValueError(f'Bundle already processed at this machine for one of its operations')

    # Step 7: Bulk create one Serial record per assigned operation
    serials = [
        models.Serial(
            Employee=allotment.Employee,
            Bundle=bundle,
            Machine=allotment.Machine,
            Operation=bo.Operation,
            CardUID=cardUID,
            Box=espBox,
        )
        for bo in boxOperations
    ]
    models.Serial.objects.bulk_create(serials)

    total = bundle.Cut.NoOfPlies * len(serials)
    return f'Bundle recorded: {total} pieces'
