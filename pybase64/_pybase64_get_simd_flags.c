#include "_pybase64_get_simd_flags.h"

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

uint32_t pybase64_get_simd_flags(void)
{
	uint32_t result = 0U;
	uint32_t eax, ebx, ecx, edx;
	uint32_t max_level;

	/* get max level */
	cpuid_(0U, 0U, &max_level, &ebx, &ecx, &edx);

	if (max_level >= 1) {
		cpuid_(1U, 0U, &eax, &ebx, &ecx, &edx);
		if (edx & 0x04000000U) {
			result |= PYBASE64_SSE2;
		}
		if (ecx & 0x00000001U) {
			result |= PYBASE64_SSE3;
		}
		if (ecx & 0x00000200U) {
			result |= PYBASE64_SSSE3;
		}
		if (ecx & 0x00080000) {
			result |= PYBASE64_SSE41;
		}
		if (ecx & 0x00100000) {
			result |= PYBASE64_SSE42;
		}
		if (ecx & 0x08000000) { /* OSXSAVE (implies XSAVE/XRESTOR/XGETBV) */
			uint64_t xcr_mask = _xgetbv(0U /* XFEATURE_ENABLED_MASK/XCR0 */);

			if (xcr_mask & 6U) { /* XMM/YMM saved by OS */
				if (ecx & 0x10000000U) {
					result |= PYBASE64_AVX;
				}
			}
		}
	}

	if (max_level >= 7) {
		cpuid_(7U, 0U, &eax, &ebx, &ecx, &edx);
		if (result & PYBASE64_AVX) { /* check AVX supported for YMM saved by OS */
				if (ebx & 0x00000020U) {
					result |= PYBASE64_AVX2;
				}
		}
	}

	return result;
}
#else
/* default version */
uint32_t pybase64_get_simd_flags(void)
{
	return 0U;
}
#endif
