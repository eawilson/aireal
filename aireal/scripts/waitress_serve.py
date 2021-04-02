import waitress
import importlib
import sys



def main():
    if len(sys.argv) < 2:
        raise RuntimeError("No application specified.")
    #kw, args = waitress.adjustments.Adjustments.parse_args(sys.argv[1:])
    #pdb.set_trace()
    target = sys.argv[-1]
    keys = [arg.lstrip("-").replace("-", "_") for arg in sys.argv[1:-1:2]]
    values = sys.argv[2:-1:2]
    if len(keys) != len(values):
        raise RuntimeError("Missing argument value.")

    colon_index = target.find(":")
    module_name = target[:colon_index]
    entry_point = target[colon_index+1:]
    if "(" not in entry_point:
        entry_point = f"{entry_point}()"
    module = importlib.import_module(module_name)
    app = eval(entry_point, vars(module))
    
    waitress.serve(app, **dict(zip(keys, values)))
    


if __name__ == "__main__":
    main()
