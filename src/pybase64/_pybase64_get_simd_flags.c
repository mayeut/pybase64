#include "_pybase64_get_simd_flags.h"
#include <config.h>

#if defined(__x86_64__) || defined(__i386__) || defined(_M_IX86) || defined(_M_X64)
/* x86 version */
#if defined(_MSC_VER)
#include <intrin.h> /* cpuid */
static void cpuid_(uint32_t leaf, uint32_t subleaf, uint32_t* eax, uint32_t* ebx, uint32_t* ecx, uint32_t* edx)
{
	int info[4];
	__cpuidex(info, (int)leaf, (int)subleaf);
	*eax = (uint32_t)info[0];
	*ebx = (uint32_t)info[1];
	*ecx = (uint32_t)info[2];
	*edx = (uint32_t)info[3];
}
#elif defined(__GNUC__)
#include <cpuid.h> /* __cpuid_count */
static void cpuid_(uint32_t leaf, uint32_t subleaf, uint32_t* eax, uint32_t* ebx, uint32_t* ecx, uint32_t* edx)
{
	__cpuid_count(leaf, subleaf, *eax, *ebx, *ecx, *edx);
}
static uint64_t _xgetbv (uint32_t index)
{
	uint32_t eax, edx;
	__asm__ __volatile__("xgetbv" : "=a"(eax), "=d"(edx) : "c"(index));
	return ((uint64_t)edx << 32) | eax;
}
#else
	/* not supported yet */
static void cpuid_(uint32_t leaf, uint32_t subleaf, uint32_t* eax, uint32_t* ebx, uint32_t* ecx, uint32_t* edx)
{
	(void)subleaf;
	(void)ebx;
	(void)ecx;
	(void)edx;

	if (leaf == 0) {
		*eax = 0U; /* max-level 0 */
	}
}
static uint64_t _xgetbv (uint32_t index)
{
	(void)index;
	return 0U;
}
#endif

#define PB64_SSE2_BIT_LVL1_EDX       (UINT32_C(1) << 26)
#define PB64_SSE3_BIT_LVL1_ECX       (UINT32_C(1) << 0)
#define PB64_SSSE3_BIT_LVL1_ECX      (UINT32_C(1) << 9)
#define PB64_SSE41_BIT_LVL1_ECX      (UINT32_C(1) << 19)
#define PB64_SSE42_BIT_LVL1_ECX      (UINT32_C(1) << 20)
#define PB64_AVX_BIT_LVL1_ECX        (UINT32_C(1) << 28)
#define PB64_AVX2_BIT_LVL7_EBX       (UINT32_C(1) << 5)
#define PB64_AVX512F_BIT_LVL7_EBX    (UINT32_C(1) << 16)
#define PB64_AVX512VL_BIT_LVL7_EBX   (UINT32_C(1) << 31)
#define PB64_AVX512VBMI_BIT_LVL7_ECX (UINT32_C(1) << 1)
#define PB64_OSXSAVE_BIT_LVL1_ECX    (UINT32_C(1) << 27)

#define PB64_XCR0_SSE_BIT       (UINT64_C(1) << 1)
#define PB64_XCR0_AVX_BIT       (UINT64_C(1) << 2)
#define PB64_XCR0_OPMASK_BIT    (UINT64_C(1) << 5)
#define PB64_XCR0_ZMM_HI256_BIT (UINT64_C(1) << 6)
#define PB64_XCR0_HI16_ZMM_BIT  (UINT64_C(1) << 7)

#define PB64_XCR0_AVX_SUPPORT_MASK    (PB64_XCR0_SSE_BIT | PB64_XCR0_AVX_BIT)
#define PB64_XCR0_AVX512_SUPPORT_MASK (PB64_XCR0_AVX_SUPPORT_MASK | PB64_XCR0_OPMASK_BIT | PB64_XCR0_ZMM_HI256_BIT | PB64_XCR0_HI16_ZMM_BIT)

#define PB64_CHECK(reg_, bits_) (((reg_) & (bits_)) == (bits_))

uint32_t pybase64_get_simd_flags(void)
{
	uint32_t result = 0U;
	uint32_t eax, ebx, ecx, edx;
	uint32_t max_level;
	uint64_t xcr0 = 0U;

	/* get max level */
	cpuid_(0U, 0U, &max_level, &ebx, &ecx, &edx);

	if (max_level >= 1) {
		cpuid_(1U, 0U, &eax, &ebx, &ecx, &edx);
		if (PB64_CHECK(edx, PB64_SSE2_BIT_LVL1_EDX)) {
			result |= PYBASE64_SSE2;
		}
		if (PB64_CHECK(ecx, PB64_SSE3_BIT_LVL1_ECX)) {
			result |= PYBASE64_SSE3;
		}
		if (PB64_CHECK(ecx, PB64_SSSE3_BIT_LVL1_ECX)) {
			result |= PYBASE64_SSSE3;
		}
		if (PB64_CHECK(ecx, PB64_SSE41_BIT_LVL1_ECX)) {
			result |= PYBASE64_SSE41;
		}
		if (PB64_CHECK(ecx, PB64_SSE42_BIT_LVL1_ECX)) {
			result |= PYBASE64_SSE42;
		}

		if (PB64_CHECK(ecx, PB64_OSXSAVE_BIT_LVL1_ECX)) { /* OSXSAVE (implies XSAVE/XRESTOR/XGETBV) */
			xcr0 = _xgetbv(0U /* XFEATURE_ENABLED_MASK/XCR0 */);

			if (PB64_CHECK(xcr0, PB64_XCR0_AVX_SUPPORT_MASK)) { /* XMM/YMM saved by OS */
				if (ecx & PB64_AVX_BIT_LVL1_ECX) {
					result |= PYBASE64_AVX;
				}
			}
		}
	}

	if (max_level >= 7) {
		cpuid_(7U, 0U, &eax, &ebx, &ecx, &edx);
		if (result & PYBASE64_AVX) { /* check AVX supported for YMM saved by OS */
			if (PB64_CHECK(ebx, PB64_AVX2_BIT_LVL7_EBX)) {
				result |= PYBASE64_AVX2;
			}
			if (PB64_CHECK(xcr0, PB64_XCR0_AVX512_SUPPORT_MASK)) {/* OpMask/ZMM/ZMM16-31 saved by OS */
				if (PB64_CHECK(ebx, PB64_AVX512F_BIT_LVL7_EBX) && PB64_CHECK(ebx, PB64_AVX512VL_BIT_LVL7_EBX) && PB64_CHECK(ecx, PB64_AVX512VBMI_BIT_LVL7_ECX)) {
					result |= PYBASE64_AVX512VBMI;
				}
			}
		}
	}

	return result;
}
#else
/* default version */
uint32_t pybase64_get_simd_flags(void)
{
#if BASE64_WITH_NEON64 || defined(__ARM_NEON__) || defined(__ARM_NEON)
    return PYBASE64_NEON;
#endif
	return 0U;
}
#endif
