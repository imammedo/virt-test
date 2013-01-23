/*
 * Test routine
 *
 * Copyright Red Hat, Inc. 2013
 *
 * Authors:
 *  Igor Mammedov <imammedo@redhat.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2 or later.
 * See the COPYING file in the top-level directory.
 */

#include "main.h"


typedef struct {
    unsigned int eax;
    unsigned int count;
} level_t;

/* array must be sorted by eax field */
static level_t levels[] = {
    { 0, 0 },
    { 1, 0 },
    { 2, 0 },
    { 4, 0 },
    { 4, 1 },
    { 4, 2 },
    { 5, 0 },
    { 6, 0 },
    { 7, 0 },
    { 9, 0 },
    { 0xA, 0 },
    { 0xD, 0 },
    { 0x80000000, 0 },
    { 0x80000001, 0 },
    { 0x80000002, 0 },
    { 0x80000003, 0 },
    { 0x80000004, 0 },
    { 0x80000005, 0 },
    { 0x80000006, 0 },
    { 0x80000008, 0 },
    { 0x8000000A, 0 },
    { 0xC0000000, 0 },
    { 0xC0000001, 0 },
    { 0xC0000002, 0 },
    { 0xC0000003, 0 },
    { 0xC0000004, 0 },
};

void test()
{
    unsigned int eax, ebx, ecx, edx, i;
    unsigned int level = 0, xlevel = 0, x2level = 0;

    printf("CPU:\n");
    for (i=0; i < sizeof(levels)/sizeof(*levels); i++) {
        unsigned int in_eax = levels[i].eax;


        if ((in_eax > level) && (in_eax < 0x80000000)) {
            continue;
        } else if ((in_eax > xlevel) && (in_eax < 0xC0000000) &&
                   (in_eax > 0x80000000) ) {
            continue;
        } else if ((in_eax > x2level) && (in_eax <= 0xFFFFFFFF) &&
                   (in_eax > 0xC0000000)) {
            break;
        }

        asm("cpuid"
            : "=a" (eax), "=b" (ebx), "=c" (ecx), "=d" (edx)
            : "a" (in_eax), "c" (levels[i].count));

        printf("   0x%08x 0x%02x: eax=0x%08x ebx=0x%08x"
               " ecx=0x%08x edx=0x%08x\n", in_eax,
               levels[i].count, eax, ebx, ecx, edx);

        if (in_eax == 0) {
            level = eax;
        }
        if (in_eax == (0x80000000 & eax)) {
            xlevel = eax;
        }
        if (in_eax == (0xC0000000 & eax)) {
            x2level = eax;
        }
   }
}
