from ginga.util.six.moves import filter
import numpy

def cmp_num(x, y):
    return int(numpy.sign(x - y))

def qsort(l, cmp_fn=cmp_num):
    i = len(l)
    if i == 0:
        return l
    pivot = i // 2
    elt = l[pivot]
    lt = list(filter(lambda x: cmp_fn(x, elt) == -1, l))
    eq = list(filter(lambda x: cmp_fn(x, elt) == 0, l))
    gt = list(filter(lambda x: cmp_fn(x, elt) == 1, l))

    return qsort(lt, cmp_fn=cmp_fn) + eq + qsort(gt, cmp_fn=cmp_fn)
