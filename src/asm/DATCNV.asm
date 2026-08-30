DATCNV   TITLE 'JULIAN / GREGORIAN DATE CONVERSION'
***********************************************************************
*                                                                     *
*  DATCNV   CONVERT BETWEEN CCYYMMDD AND CCYYDDD.                     *
*                                                                     *
*  LINKAGE  STANDARD.  R1 -> PARAMETER LIST, WORD 0 -> PARM AREA.     *
*           R13 -> CALLER SAVE AREA.  R14 RETURN.  R15 ENTRY/RC.      *
*                                                                     *
*  FUNCTION BYTE AT +0    C'J'  GREGORIAN TO JULIAN                   *
*                        C'G'  JULIAN TO GREGORIAN                    *
*                                                                     *
*  RETURN   0  CONVERTED                                              *
*           8  FUNCTION OR DATE INVALID                               *
*                                                                     *
***********************************************************************
         SPACE 1
R0       EQU   0
R1       EQU   1
R2       EQU   2
R3       EQU   3
R4       EQU   4
R5       EQU   5
R6       EQU   6
R7       EQU   7
R11      EQU   11
R12      EQU   12
R13      EQU   13
R14      EQU   14
R15      EQU   15
         SPACE 1
DATCNV   CSECT
         STM   R14,R12,12(R13)
         LR    R12,R15
         USING DATCNV,R12
         LA    R11,SAVEA
         ST    R13,4(,R11)
         ST    R11,8(,R13)
         LR    R13,R11
         SPACE 1
         L     R2,0(,R1)                A(PARM AREA)
         USING PARM,R2
         MVI   PF16,C'0'
         SPACE 1
         CLI   PF00,C'J'
         BE    TOJUL
         CLI   PF00,C'G'
         BE    TOGRG
         B     BADRC
         SPACE 1
***********************************************************************
*  GREGORIAN TO JULIAN.  UNPACK THE COMPONENTS, ACCUMULATE THE FULL   *
*  MONTHS AHEAD OF THE SUBJECT MONTH, THEN ADD THE DAY.               *
***********************************************************************
TOJUL    PACK  DWD,PF01(4)              CCYY
         CVB   R4,DWD
         PACK  DWD,PF01+4(2)            MM
         CVB   R5,DWD
         PACK  DWD,PF01+6(2)            DD
         CVB   R6,DWD
         LTR   R5,R5
         BNP   BADRC
         CH    R5,=H'12'
         BH    BADRC
         BAL   R14,LEAP
         SR    R7,R7                    DAY ACCUMULATOR
         LR    R3,R5
         BCTR  R3,0                     FULL MONTHS ONLY
         LTR   R3,R3
         BZ    TOJ020
         LA    R1,MTAB
TOJ010   AH    R7,0(,R1)
         LA    R1,2(,R1)
         BCT   R3,TOJ010
TOJ020   CH    R5,=H'2'                 PAST FEBRUARY
         BNH   TOJ030
         AR    R7,R9                    ADD LEAP DAY
TOJ030   AR    R7,R6
         MH    R4,=H'1000'
         AR    R4,R7
         CVD   R4,DWD
         UNPK  PF09(7),DWD
         OI    PF09+6,X'F0'
         B     EXIT
         SPACE 1
***********************************************************************
*  JULIAN TO GREGORIAN.  SUBTRACT WHOLE MONTHS UNTIL THE REMAINDER    *
*  NO LONGER SPANS ONE.                                               *
***********************************************************************
TOGRG    PACK  DWD,PF09(7)
         CVB   R4,DWD
         SR    R5,R5
         LR    R3,R4
         SRDA  R4,32
         D     R4,=F'1000'              R5 = CCYY, R4 = DDD
         LR    R7,R4                    DAY OF YEAR
         LR    R4,R5                    YEAR
         BAL   R14,LEAP
         LTR   R7,R7
         BNP   BADRC
         LA    R5,1                     MONTH INDEX
         LA    R1,MTAB
TOG010   LH    R3,0(,R1)
         CH    R5,=H'2'
         BNE   TOG020
         AR    R3,R9                    FEBRUARY LEAP DAY
TOG020   CR    R7,R3
         BNH   TOG030
         SR    R7,R3
         LA    R5,1(,R5)
         LA    R1,2(,R1)
         CH    R5,=H'12'
         BNH   TOG010
         B     BADRC
TOG030   MH    R4,=H'10000'
         LR    R3,R5
         MH    R3,=H'100'
         AR    R4,R3
         AR    R4,R7
         CVD   R4,DWD
         UNPK  PF01(8),DWD
         OI    PF01+7,X'F0'
         B     EXIT
         SPACE 1
***********************************************************************
*  LEAP  R4 = YEAR ON ENTRY.  R9 = 1 WHEN FEBRUARY HAS 29 DAYS.       *
***********************************************************************
LEAP     SR    R9,R9
         LR    R3,R4
         SRDA  R2,32
         D     R2,=F'4'
         LTR   R2,R2
         BNZ   LEAPX
         LA    R9,1
         LR    R3,R4
         SRDA  R2,32
         D     R2,=F'100'
         LTR   R2,R2
         BNZ   LEAPX
         SR    R9,R9
         LR    R3,R4
         SRDA  R2,32
         D     R2,=F'400'
         LTR   R2,R2
         BNZ   LEAPX
         LA    R9,1
LEAPX    BR    R14
         SPACE 1
BADRC    MVI   PF16,C'8'
         SPACE 1
EXIT     L     R13,4(,R13)
         LM    R14,R12,12(R13)
         SR    R15,R15
         BR    R14
         SPACE 1
SAVEA    DS    18F
DWD      DS    D
MTAB     DC    H'31,28,31,30,31,30,31,31,30,31,30,31'
         SPACE 1
***********************************************************************
*  PARAMETER AREA.  24 BYTES.  MAPPED BY DISPLACEMENT.                *
***********************************************************************
PARM     DSECT
PF00     DS    CL1                      +0
PF01     DS    CL8                      +1
PF09     DS    CL7                      +9
PF16     DS    CL1                      +16
PF17     DS    CL7                      +17
         SPACE 1
         END   DATCNV
