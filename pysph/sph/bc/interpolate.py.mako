<%
vec_name = [
  'Uhat', 'U', 'P'
]
u_vec = [
  'u', 'v', 'w'
    ]
x_vec = [
  'x', 'y', 'z'
]
%>
## ****************************
## ******* imports ***********
## ****************************
# This is file is generated from interpolate.py.mako
# Do not edit this file
from pysph.sph.equation import Equation
from compyle.api import declare
from pysph.sph.wc.linalg import gj_solve, augmented_matrix\
%for var in vec_name:
## ****************************
## ******* setup ***********
## ****************************
<%hat = '' ; h = '' ; acc = '' ; factor = '' ; vec_var = () ; vec_x = x_vec;%>
% if (var == 'Uhat') or (var == 'Auhat'):
<% hat = 'hat'; h = 'h' %>
% endif
% if (var == 'Uhat')or (var == 'U'):
<% vec_var = u_vec; factor = '-1. * ' %>
% endif
% if (var == 'P'):
<% vec_var = ['p'] %>
% endif
## ****************************
## * function Evaluate ********
## ****************************
<%array5 = ''%>\
%for u in vec_var:
<%array5=array5+', d_'+acc+u+h+'o'%>\
<%array5=array5+', d_B'+acc+u+h%>\
% endfor
<%array6 = ''%>\
%for u in vec_var:
%if not(var == 'Rho'):
<%array6=array6+', s_'+acc+u+hat%>\
%endif
<%array6=array6+', d_B'+acc+u+h%>\
% endfor
<%array7 = ''%>\
%for u in vec_var:
<%array7=array7+', d_'+acc+u+h+'o'%>\
<%array7=array7+', d_B'+acc+u+h%>\
% endfor
class Evaluate${var}(Equation):
    def _get_helpers_(self):
        return [gj_solve, augmented_matrix]

    def __init__(self, dest, sources, dim=1):
        self.dim = dim

        super(Evaluate${var}, self).__init__(dest, sources)

    def initialize(self, d_idx${array5}):
        i = declare('int')

        for i in range(3):
            %for u in vec_var:
            d_${acc}${u}${h}o[4*d_idx+i] = 0.0
            d_B${acc}${u}${h}[4*d_idx+i] = 0.0
            % endfor

    def loop(self, d_idx, d_h, s_h, s_x, s_y, s_z, d_x, d_y, d_z, s_rho,
             s_m, s_idx, XIJ, DWIJ,
             WIJ${array6}):
        Vj = s_m[s_idx] / s_rho[s_idx]
        %for u in vec_var:
        ${acc}${u}${h}j = s_${acc}${u}${hat}[s_idx]
        %endfor
        i4 = declare('int')
        i4 = 4*d_idx

        %for u in vec_var:
        d_B${acc}${u}${h}[i4+0] += ${acc}${u}${h}j * WIJ * Vj
        d_B${acc}${u}${h}[i4+1] += ${acc}${u}${h}j * DWIJ[0] * Vj
        d_B${acc}${u}${h}[i4+2] += ${acc}${u}${h}j * DWIJ[1] * Vj
        d_B${acc}${u}${h}[i4+3] += ${acc}${u}${h}j * DWIJ[2] * Vj
        % endfor

    def post_loop(self, d_idx, d_A${array7}):
        a_mat = declare('matrix(16)')
        aug_mat = declare('matrix(20)')
        %for u in vec_var:
        b_${acc}${u}${h} = declare('matrix(4)')
        res_${acc}${u}${h} = declare('matrix(4)')
        %endfor
        i, n, i16, i4 = declare('int', 4)
        i16 = 16*d_idx
        i4 = 4*d_idx

        for i in range(16):
            a_mat[i] = d_A[i16+i]
        for i in range(20):
            aug_mat[i] = 0.0
        for i in range(4):
        %for u in vec_var:
            b_${acc}${u}${h}[i] = d_B${acc}${u}${h}[i4+i]
            res_${acc}${u}${h}[i] = 0.0
        %endfor

        n = self.dim + 1
        %for u in vec_var:
        augmented_matrix(a_mat, b_${acc}${u}${h}, n, 1, 4, aug_mat)
        gj_solve(aug_mat, n, 1, res_${acc}${u}${h})
        for i in range(4):
            d_${acc}${u}${h}o[i4+i] = res_${acc}${u}${h}[i]
        % endfor
## ****************************
## * function Extrpolate ********
## ****************************
<%array8 = ''%>\
%for u in vec_var:
<%array8=array8+', d_'+acc+u+hat%>\
% endfor
<%array9 = ''%>\
%for u in vec_var:
<%array9=array9+', d_'+acc+u+hat%>\
<%array9=array9+', d_'+acc+u+h+'o'%>\
% endfor
<%array10 = ''%>\
%for x in vec_x:
<%array10=array10+', d_'+x+'n'%>\
% endfor


class Extrapolate${var}(Equation):
    def initialize(self, d_idx${array8}):
        %for u in vec_var:
        d_${acc}${u}${hat}[d_idx] = 0.0
        % endfor

    def loop(self, d_idx${array9},
             d_disp${array10}):

      %for x in vec_x:
        del${x} = 2 * d_disp[d_idx] * d_${x}n[d_idx]
      % endfor
      %for u in vec_var:
       %if (loop.index > 0):
<% factor = '' %>
       % endif
        d_${acc}${u}${hat}[d_idx] = ${factor}(
             d_${acc}${u}${h}o[4*d_idx+0]
       %for x in vec_x:
        %if ((u=='u') or (u=='x')) and (acc==''):
             - del${x} * d_${acc}${u}${h}o[4*d_idx+${loop.index + 1}]
        %else:
             - del${x} * d_${acc}${u}${h}o[4*d_idx+${loop.index + 1}]
        %endif
       %endfor
                      )
      %endfor
## ****************************
## * function CopyfromGhost ***
## ****************************
<%array11 = ''%>\
%for u in vec_var:
<%array11=array11+', d_'+acc+u+hat%>\
<%array11=array11+', s_'+acc+u+hat%>\
% endfor
<%array12 = ''%>\
%for u in vec_var:
<%array12=array12 +'+ s_'+acc+u+hat+'[d_idx] * d_'+x_vec[loop.index]+'n[d_idx]'%>\
% endfor
<% factor = ' -1.0 *' %>\


class Copy${var}FromGhost(Equation):
    def initialize_pair(self,
                        d_idx${array11}):
    %if not ((var == 'P') or (var == 'Rho')):
     %for u in vec_var:
      %if (loop.index > 0):
<% factor = '' %>
      % endif
        d_${acc}${u}${hat}[d_idx] =${factor} s_${acc}${u}${hat}[d_idx]
     %endfor
    % else:
     %for u in vec_var:
        d_${u}[d_idx] = s_${u}[d_idx]
     % endfor
    % endif
% endfor


class UpdateMomentMatrix(Equation):
    def __init__(self, dest, sources, dim=1):
        self.dim = dim

        super(UpdateMomentMatrix, self).__init__(dest, sources)

    def initialize(self, d_idx, d_A):
        i, j = declare('int', 2)

        for i in range(4):
            for j in range(4):
                d_A[16*d_idx + j+4*i] = 0.0

    def loop(self, d_idx, s_idx, d_h, s_h, s_x, s_y, s_z, d_x, d_y,
             d_z, s_rho, s_m, d_A, XIJ, WIJ, DWIJ):
        Vj = s_m[s_idx] / s_rho[s_idx]
        i16 = declare('int')
        i16 = 16*d_idx
        d_A[i16+0] += WIJ * Vj

        d_A[i16+1] += -XIJ[0] * WIJ * Vj
        d_A[i16+2] += -XIJ[1] * WIJ * Vj
        d_A[i16+3] += -XIJ[2] * WIJ * Vj

        d_A[i16+4] += DWIJ[0] * Vj
        d_A[i16+8] += DWIJ[1] * Vj
        d_A[i16+12] += DWIJ[2] * Vj

        d_A[i16+5] += -XIJ[0] * DWIJ[0] * Vj
        d_A[i16+6] += -XIJ[1] * DWIJ[0] * Vj
        d_A[i16+7] += -XIJ[2] * DWIJ[0] * Vj

        d_A[i16+9] += -XIJ[0] * DWIJ[1] * Vj
        d_A[i16+10] += -XIJ[1] * DWIJ[1] * Vj
        d_A[i16+11] += -XIJ[2] * DWIJ[1] * Vj

        d_A[i16+13] += -XIJ[0] * DWIJ[2] * Vj
        d_A[i16+14] += -XIJ[1] * DWIJ[2] * Vj
        d_A[i16+15] += -XIJ[2] * DWIJ[2] * Vj
