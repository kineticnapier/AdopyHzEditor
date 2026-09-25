# stb_vorbis

stb_vorbis.c is pinned from nothings/stb at commit
1ee679ca2ef753a528db5ba6801e1067b40481b8.

The upstream source offers MIT or public-domain licensing. This copy has one
small guarded change: defining STB_VORBIS_SPECTRUM_ONLY omits the inverse
MDCT call after floor, residue, inverse coupling, and floor application.
Normal builds that do not define the flag retain upstream behavior.
