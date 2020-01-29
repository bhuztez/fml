class Error:

    def line_of(self, t):
        last_cr = self.text.rfind('\n', 0, t.index)
        next_cr = self.text.find('\n', t.index)
        if next_cr < 0:
            next_cr = None
        return self.text[last_cr+1: next_cr]

    def col_offset(self, t):
        last_cr = self.text.rfind('\n', 0, t.index)
        if last_cr < 0:
            last_cr = 0
        return t.index - last_cr

    def error(self, t, msg):
        raise SyntaxError(
            msg,
            ( self.filename,
              t.lineno,
              self.col_offset(t),
              self.line_of(t)
            ))
