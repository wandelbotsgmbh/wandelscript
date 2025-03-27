import wandelscript

@wandelscript.register_builtin_func
def custom_print(message: str):
    print(f"Custom print {message}")
