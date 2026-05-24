def make_base(work_dir, **kwargs):
    return f"{work_dir}/base"


def split_base(func1, **kwargs):
    return func1, len(func1)
