/* Exact nearest-neighbour placement of changed BGR pixels on a native frame.
 * Coordinates are obtained from the installed OpenCV build by the Python caller. */
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <emmintrin.h>

static int limits_ok(const int32_t *p, int n, int end) {
    if (!p || p[0] != 0 || p[n] != end) return 0;
    for (int i=0; i<n; ++i)
        if (p[i] > p[i+1] || p[i+1] > end) return 0;
    return 1;
}

static inline int same16(const uint8_t *a, const uint8_t *b) {
    const __m128i av = _mm_loadu_si128((const __m128i *)a);
    const __m128i bv = _mm_loadu_si128((const __m128i *)b);
    return _mm_movemask_epi8(_mm_cmpeq_epi8(av, bv)) == 65535;
}

int project_bgr(const uint8_t *updated, ptrdiff_t us, const uint8_t *original,
                ptrdiff_t os, uint8_t *dst, ptrdiff_t ds, int w, int h,
                int nw, int nh, const int32_t *xs, const int32_t *ys) {
    if (!updated || !original || !dst || w<=0 || h<=0 || nw<=0 || nh<=0 ||
        w>65536 || h>65536 || nw>65536 || nh>65536 ||
        us<3*w || os<3*w || ds<3*nw || !limits_ok(xs,w,nw) || !limits_ok(ys,h,nh))
        return 0;
    for (int y=0; y<h; ++y) {
        const uint8_t *a = updated+y*us, *b = original+y*os;
        const int y0=ys[y], y1=ys[y+1];
        if (y0==y1) continue;
        for (int x=0; x<w;) {
            int end = x+16 < w ? x+16 : w;
            /* Sixteen packed BGR pixels occupy three unaligned SSE2 registers. */
            if (end-x == 16 && same16(a+3*x,b+3*x) &&
                same16(a+3*x+16,b+3*x+16) && same16(a+3*x+32,b+3*x+32)) {
                x=end;
                continue;
            }
            for (; x<end; ++x) {
                const uint8_t *v=a+3*x, *prev=b+3*x;
                if (v[0]==prev[0] && v[1]==prev[1] && v[2]==prev[2]) continue;
                int first=xs[x], last=xs[x+1];
                for (int yy=y0; yy<y1; ++yy) {
                    uint8_t *pixel=dst+yy*ds+3*first;
                    for (int xx=first; xx<last; ++xx, pixel+=3) memcpy(pixel,v,3);
                }
            }
        }
    }
    return 1;
}
