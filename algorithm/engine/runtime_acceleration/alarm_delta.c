/* Lossless 32-byte temporal blocks. Header codes select zero, 2-bit, 4-bit,
 * or literal bytes. All lengths and offsets are checked before decode writes. */
#include <immintrin.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API __attribute__((visibility("default")))
#endif

static inline __m128i pack_pairs(__m256i values, int shift, int mask) {
    __m256i pairs = _mm256_or_si256(values, _mm256_srli_epi16(values, shift));
    pairs = _mm256_and_si256(pairs, _mm256_set1_epi16(mask));
    return _mm_packus_epi16(_mm256_castsi256_si128(pairs), _mm256_extracti128_si256(pairs,1));
}

API size_t alarm_delta_encode(const uint8_t *frame, uint8_t *previous,
                              size_t size, uint8_t *output, size_t capacity) {
    size_t blocks = size / 32, headers = (blocks + 3) / 4;
    if (capacity < size + headers) return 0;
    uint8_t *cursor = output + headers;
    unsigned header = 0;
    const __m256i zero = _mm256_setzero_si256();
    for (size_t i = 0; i < blocks; ++i) {
        __m256i cur = _mm256_loadu_si256((const __m256i *)(frame + i*32));
        __m256i ref = _mm256_loadu_si256((const __m256i *)(previous + i*32));
        __m256i delta = _mm256_sub_epi8(cur, ref);
        unsigned code = 0;
        if (!_mm256_testz_si256(delta, delta)) {
            _mm256_storeu_si256((__m256i *)(previous + i*32),cur);
            __m256i zig = _mm256_xor_si256(_mm256_add_epi8(delta, delta), _mm256_cmpgt_epi8(zero, delta));
            if (_mm256_testz_si256(zig, _mm256_set1_epi8(-4))) {
                __m128i pairs = pack_pairs(zig,6,15);
                __m128i packed = _mm_and_si128(_mm_or_si128(pairs, _mm_srli_epi16(pairs,4)),
                                               _mm_set1_epi16(255));
                _mm_storel_epi64((__m128i *)cursor,_mm_packus_epi16(packed,packed));
                code = 1; cursor += 8;
            } else if (_mm256_testz_si256(zig, _mm256_set1_epi8(-16))) {
                _mm_storeu_si128((__m128i *)cursor,pack_pairs(zig,4,255));
                code = 2; cursor += 16;
            } else {
                _mm256_storeu_si256((__m256i *)cursor,cur);
                code = 3; cursor += 32;
            }
        }
        unsigned shift = (unsigned)(i & 3) * 2;
        header |= code << shift;
        if (shift == 6 || i + 1 == blocks) {
            output[i >> 2] = (uint8_t)header;
            header = 0;
        }
    }
    size_t tail = size - blocks*32;
    memcpy(cursor,frame+blocks*32,tail);
    memcpy(previous+blocks*32,frame+blocks*32,tail);
    return (size_t)(cursor-output)+tail;
}

static inline __m256i expand_pairs(__m128i packed, unsigned bits) {
    __m256i words = _mm256_cvtepu8_epi16(packed);
    __m256i mask = _mm256_set1_epi16((short)((1u<<bits)-1));
    return _mm256_or_si256(_mm256_and_si256(words,mask),
                           _mm256_slli_epi16(_mm256_and_si256(_mm256_srli_epi16(words,bits),mask),8));
}

API int alarm_delta_decode(const uint8_t *source, size_t bytes, const uint8_t *previous,
                           size_t size, uint8_t *out) {
    size_t blocks = size/32, headers = (blocks+3)/4;
    if (headers > bytes) return 0;
    size_t pos = headers;
    const __m256i zero = _mm256_setzero_si256();
    for (size_t i = 0; i < blocks; ++i) {
        unsigned code = (source[i>>2] >> (2*(i&3))) & 3;
        size_t needed = code == 3 ? 32 : code*8;
        if (bytes-pos < needed) return 0;
        __m256i values;
        if (code == 3) {
            values = _mm256_loadu_si256((const __m256i *)(source+pos));
        } else if (code || out != previous) {
            values = _mm256_loadu_si256((const __m256i *)(previous+i*32));
            if (code) {
                __m128i pairs;
                if (code == 1) {
                    __m128i b = _mm_loadl_epi64((const __m128i *)(source+pos));
                    pairs = _mm256_castsi256_si128(expand_pairs(b,4));
                } else {
                    pairs = _mm_loadu_si128((const __m128i *)(source+pos));
                }
                __m256i zig = expand_pairs(pairs,code==1?2:4);
                __m256i sign = _mm256_sub_epi8(zero,_mm256_and_si256(zig,_mm256_set1_epi8(1)));
                __m256i mag = _mm256_and_si256(_mm256_srli_epi16(zig,1),_mm256_set1_epi8(127));
                values = _mm256_add_epi8(values,_mm256_xor_si256(mag,sign));
            }
        } else {
            continue;
        }
        _mm256_storeu_si256((__m256i *)(out+i*32),values);
        pos += needed;
    }
    if (bytes-pos != size-blocks*32) return 0;
    memcpy(out+blocks*32,source+pos,bytes-pos);
    return 1;
}
