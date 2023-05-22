from transition_device import S4224
from transition_device import LIB4424


def create_device(**kwargs):

    if kwargs['device_model']['device_model_id'] == 1:
        return S4224(**kwargs)
    elif kwargs['device_model']['device_model_id'] == 6:
        return LIB4424(**kwargs)
    else:
        print("Error: The Device is Not Suported.")
