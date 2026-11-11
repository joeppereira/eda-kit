# Third-Party Notices

eda-kit redistributes / derives from the following components. All are permissively
licensed (BSD-3-Clause) and redistributed here with attribution per their terms.

## ASAP7 predictive PDK — `pdk/asap7/*.card`
BSIM-CMG model cards derived from the ASAP7 7nm predictive PDK.
- **Copyright 2020 Lawrence T. Clark, Vinay Vashishtha, Arizona State University.**
- Source: https://github.com/The-OpenROAD-Project/asap7_pdk_r1p7
- License: BSD-3-Clause (full text below).
- Predictive/academic PDK — **not** a foundry process; never for sign-off.

## GT2N 2nm GAA-nanosheet PDK — `pdk/gt2n/*.card`, `pdk/gt2n_src/*.sp`
2nm GAA-nanosheet BSIM-CMG cards; the `pdk/gt2n/` cards are translated HSPICE→OSDI
from the GT2N sources (see `build_gt2n.py`); `pdk/gt2n_src/` are the originals.
- **Copyright 2025 Dongwon Jang, Nahid Shazon, Azad Naeemi, Georgia Institute of Technology.**
- Source: https://github.com/azadnaeemi/GT2N
- License: BSD-3-Clause (full text below).

## Tools fetched by `setup.sh` (NOT redistributed in this repo)
Downloaded into `.tools/` (gitignored) at setup time; their own licenses apply:
- **BSIM-CMG** compact model — BSD, UC Berkeley (dwarning/VA-Models).
- **OpenVAF-Reloaded** — Verilog-A compiler (its own license; used as a tool, not linked).
- **PTM** / predictive sources for calibrated intermediate-node cards — academic.

---

## BSD-3-Clause (applies to ASAP7 and GT2N above)

```
Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of
   conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of
   conditions and the following disclaimer in the documentation and/or other materials
   provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors may be used
   to endorse or promote products derived from this software without specific prior
   written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
