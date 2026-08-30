PENACC   TITLE 'PACKED DECIMAL PENALTY ACCUMULATION'
***********************************************************************
*                                                                     *
*  PENACC   APPLY A RATE TO A LIABILITY AMOUNT AND ROLL THE RESULT    *
*           INTO A RUNNING PENALTY ACCUMULATOR.                       *
*                                                                     *
*  LINKAGE  STANDARD.  R1 -> PARAMETER LIST, WORD 0 -> PARM AREA.     *
*           R13 -> CALLER SAVE AREA.  R14 RETURN.  R15 ENTRY/RC.      *
*                                                                     *
*  PARM     +0  PL7   BASE AMOUNT        S9(11)V99                    *
*           +7  PL3   RATE               S9(1)V9999                   *
*          +10  PL6   ACCUMULATOR        S9(9)V99                     *
*          +16  PL6   THIS AMOUNT        S9(9)V99                     *
*          +22  CL1   RETURN CODE                                     *
*                                                                     *
*  RETURN   0  APPLIED                                                *
*           8  BASE NEGATIVE, AMOUNT ZEROED                           *
*                                                                     *
***********************************************************************
         SPACE 1
R0       EQU   0
R1       EQU   1
R2       EQU   2
R11      EQU   11
R12      EQU   12
R13      EQU   13
R14      EQU   14
R15      EQU   15
         SPACE 1
PENACC   CSECT
         STM   R14,R12,12(R13)
         LR    R12,R15
         USING PENACC,R12
         LA    R11,SAVEA
         ST    R13,4(,R11)
         ST    R11,8(,R13)
         LR    R13,R11
         SPACE 1
         L     R2,0(,R1)                A(PARM AREA)
         USING PARM,R2
         MVI   PF22,C'0'
         SPACE 1
         CP    PF00(7),=P'0'            BASE MUST NOT BE NEGATIVE
         BNL   CALC
         MVI   PF22,C'8'
         ZAP   PF16(6),=P'0'
         B     EXIT
         SPACE 1
***********************************************************************
*  PRODUCT CARRIES SIX DECIMAL PLACES.  SRP ROUNDS BACK TO TWO BY     *
*  SHIFTING RIGHT FOUR WITH A ROUNDING FACTOR OF FIVE.                *
***********************************************************************
CALC     ZAP   WORK(16),PF00(7)         BASE
         MP    WORK(16),PF07(3)         TIMES RATE
         SRP   WORK(16),64-4,5          SHIFT RIGHT 4, ROUND
         ZAP   PF16(6),WORK(16)         THIS AMOUNT
         AP    PF10(6),PF16(6)          ROLL INTO ACCUMULATOR
         SPACE 1
EXIT     L     R13,4(,R13)
         LM    R14,R12,12(R13)
         SR    R15,R15
         BR    R14
         SPACE 1
SAVEA    DS    18F
WORK     DS    PL16
         SPACE 1
***********************************************************************
*  PARAMETER AREA.  32 BYTES.  MAPPED BY DISPLACEMENT.                *
***********************************************************************
PARM     DSECT
PF00     DS    PL7                      +0
PF07     DS    PL3                      +7
PF10     DS    PL6                      +10
PF16     DS    PL6                      +16
PF22     DS    CL1                      +22
PF23     DS    CL9                      +23
         SPACE 1
         END   PENACC
