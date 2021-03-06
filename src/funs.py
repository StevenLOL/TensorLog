# (C) William W. Cohen and Carnegie Mellon University, 2016
#
# functions, which support evaluation and backprop
#

import sys
import logging
import traceback

import ops
import config
import mutil


conf = config.Config()
conf.trace = False;         conf.help.trace =         "Print debug info during function eval"
conf.long_trace = False;    conf.help.long_trace =    "Print output of functions during eval - only for small tasks"

class Function(object):
    """The tensorlog representation of a function. This supports eval and
    evalGrad operations, and take a list of input values as the inputs.
    """
    def eval(self,db,values):
        if conf.trace:
            print "Invoking %s:\n%s" % (str(self),"\n. . ".join(self.pprint()))
        result = self._doEval(db,values)
        if conf.trace:
            print "Function completed:\n%s" % "\n. . ".join(self.pprint())
            if conf.long_trace:
                for k,v in enumerate(values):
                    print '. input',k+1,':',db.matrixAsSymbolDict(values[k])
                print '. result :',db.matrixAsSymbolDict(result)
        return result
    def backprop(self,delta,gradAccum):
        if conf.trace:
            print "Backprop %s:\n%s" % (str(self),"\n. . ".join(self.pprint()))
        result = self._doBackprop(delta,gradAccum)
        if conf.trace:
            print "Backprop completed:\n%s" % "\n. . ".join(self.pprint())
        return result
    def pprint(self,depth=0):
        """Return list of lines in a pretty-print of the function.
        """
        assert False, 'abstract method called'

class OpSeqFunction(Function):

    """A function defined by executing a sequence of operators."""
    def __init__(self,opInputs,opOutput,ops,rule=None):
        self.opInputs = opInputs    #initial bindings to insert in Envir
        self.opOutput = opOutput  #finding bindings which indicate the output
        self.ops = ops
        self.result = None
        self.rule = rule #recorded for debug/trace
        self.opEnv = None #caches environment to evaluate the ops
    def __repr__(self):
        shortOps = '[%r,...,%r]' % (self.ops[0],self.ops[-1])
        return 'OpSeqFunction(%r,%r,%r)' % (self.opInputs,self.opOutput,shortOps)
    def pprint(self,depth=0):
        top = ('| '*depth) + '%s = OpSeqFunction(%r):' % (self.opOutput,self.opInputs)
        if self.rule: top = top + '\t\t// ' + str(self.rule)
        return [top] + reduce(lambda x,y:x+y, map(lambda o:[s for s in o.pprint(depth+1)], self.ops))
        #was: return [top] + map(lambda o:('| '*(depth+1))+o.pprint(), self.ops)
    def _doEval(self,db,values):
        #eval expression
        self.opEnv = ops.Envir(db)
        self.opEnv.bindList(self.opInputs,values)
        i=0
        for op in self.ops:
            i+=1
            #if TRACE: logging.debug("calling %d of %d %s from %s" % (i,len(self.ops),str(op),str(self)))
            op.eval(self.opEnv)
        self.result = self.opEnv[self.opOutput]
        return self.result
    def _doBackprop(self,delta,gradAccum):
        self.opEnv.delta[self.opOutput] = delta
        n = len(self.ops)
        for i in range(n):
            op = self.ops[n-i-1]
            #print 'calling backprop on op',n-i-1,str(op)
            op.backprop(self.opEnv,gradAccum)
        assert len(self.opInputs)==1, 'bp for multiple input functions not implemented'
        return self.opEnv.delta[self.opInputs[0]]

class NullFunction(OpSeqFunction):
    """Returns an all-zeros vector."""
    def __init__(self,lhsMode):
        self.opInputs = [('X%d' % i)  for i in range(lhsMode.arity) if lhsMode.isInput(i)]
        self.opOutput = 'Y'
        self.ops = [ops.AssignZeroToVar(self.opOutput)]
    def __repr__(self):
        return 'NullFunction()'
    def pprint(self,depth=0):
        return [('| '*depth) + repr(self)]
    def _doEval(self,db,values):
        self.result = db.zeros(mutil.numRows(values[0]))
        return self.result
    def _doBackprop(self,delta,gradAccum):
        return self.result


class SumFunction(Function):
    """A function which computes the sum of a bunch of other functions."""
    def __init__(self,funs):
        self.funs = funs
        self.result = None
    def __repr__(self):
        return 'SumFunction(%r)' % self.funs
    def pprint(self,depth=0):
        return [('| '*depth) + 'SumFunction:'] + reduce(lambda x,y:x+y, map(lambda f:f.pprint(depth=depth+1), self.funs))
    def _doEval(self,db,values):
        addends = map(lambda f:f.eval(db,values), self.funs)
        accum = addends[0]
        for i in range(1,len(addends)):
            accum = accum + addends[i]
        self.result = accum
        return self.result
    def _doBackprop(self,delta,gradAccum):
        addends = map(lambda f:f.backprop(delta,gradAccum), self.funs)
        accum = addends[0]
        for i in range(1,len(addends)):
            accum = accum + addends[i]
        return accum

class SoftmaxFunction(Function):
    """A function which computes row-wise softmax."""
    def __init__(self,fun):
        self.fun = fun
        self.result = None
    def __repr__(self):
        return 'SoftmaxFunction(%r)' % self.fun
    def pprint(self,depth=0):
        return [('| '*depth) + 'SoftmaxFunction:'] + self.fun.pprint(depth=depth+1)
    def _doEval(self,db,values):
        unnorm = self.fun.eval(db,values)
        #if TRACE: print "pre-softmax unnorm: %s" % mutil.summary(unnorm)
        self.result = mutil.softmax(db,unnorm)
        return self.result
    def _doBackprop(self,delta):
        # see comments for learner.crossEntropyGrad
        assert False, 'should not call this directly'

